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


def _location_ok(job: Job, config: dict) -> bool:
    """Decide if a job's location works for someone based in Pakistan.

    Rules (in order):
      * A job whose location mentions Pakistan (or a Pakistani city) is always OK.
      * An on-site job outside Pakistan is rejected.
      * A remote job is OK if its required location is global/worldwide OR names a
        region that includes Pakistan (Asia / APAC).
      * A remote job is REJECTED if its required location names another specific
        country/region (USA, Brazil, Europe, ...).
      * A remote job with a generic/unspecified location ('Remote', blank) is kept
        only if keep_generic_remote is true.
    """
    loc = job.location.lower()

    local = [t.lower() for t in config.get("local_terms", [])]
    if any(t in loc for t in local):
        return True

    if not job.remote:
        return False  # on-site and not in Pakistan

    worldwide = [t.lower() for t in config.get("worldwide_terms", [])]
    regions = [t.lower() for t in config.get("include_regions", [])]
    if any(t in loc for t in worldwide) or any(t in loc for t in regions):
        return True

    restricted = [t.lower() for t in config.get("restricted_terms", [])]
    if any(t in loc for t in restricted):
        return False

    # Generic remote with no country named ("Remote", "", "N/A").
    return bool(config.get("keep_generic_remote", True))


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
    if not _location_ok(job, config):
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
