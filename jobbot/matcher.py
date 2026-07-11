"""Scoring and filtering: decide which jobs are worth an alert."""

from __future__ import annotations

import logging
import re

from .models import Job

log = logging.getLogger("jobbot.matcher")


def _contains(haystack: str, needle: str) -> bool:
    """Word-ish containment. Handles skills with dots like 'node.js'."""
    needle = needle.lower().strip()
    if not needle:
        return False
    # Use a boundary-aware search so 'ai' doesn't match 'maintain'.
    pattern = r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def score_job(job: Job, config: dict) -> Job:
    """Attach a score and the list of matched skills to a job (in place)."""
    text = job.haystack
    matched = []
    total = 0
    for skill, weight in config.get("skills", {}).items():
        if _contains(text, str(skill)):
            matched.append(str(skill))
            total += int(weight)
    job.score = total
    job.matched_skills = matched
    return job


def passes(job: Job, config: dict) -> bool:
    """Apply every hard filter. Returns True if the job should be alerted."""
    text = job.haystack

    # 1) Must mention at least one role keyword.
    roles = config.get("role_keywords", [])
    if roles and not any(_contains(text, r) for r in roles):
        return False

    # 2) Hard exclusions.
    for bad in config.get("negative_keywords", []):
        if _contains(text, bad):
            return False

    # 3) Location / remote filter.
    if config.get("require_remote_or_location", True):
        allowed = config.get("allowed_locations", [])
        loc_text = (job.location + " " + " ".join(job.tags)).lower()
        location_ok = job.remote or any(a.lower() in loc_text for a in allowed)
        if not location_ok:
            return False

    # 4) Freshness.
    max_age = config.get("max_age_days")
    if max_age and job.age_days is not None and job.age_days > float(max_age):
        return False

    # 5) Score threshold.
    if job.score < int(config.get("min_score", 1)):
        return False

    return True


def match(jobs: list[Job], config: dict) -> list[Job]:
    """Score, filter, de-dup within this batch, and rank by score."""
    results: list[Job] = []
    seen: set[str] = set()
    for job in jobs:
        if not job.url or job.uid in seen:
            continue
        seen.add(job.uid)
        score_job(job, config)
        if passes(job, config):
            results.append(job)
    results.sort(key=lambda j: j.score, reverse=True)
    log.info("matched %d of %d jobs", len(results), len(jobs))
    return results
