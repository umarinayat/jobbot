"""Job sources.

Each fetcher returns a list of normalized ``Job`` objects and is written
defensively: any single source failing (network hiccup, markup change, rate
limit) logs a warning and returns an empty list rather than crashing the run.
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Callable

import requests

from .models import Job, parse_date

log = logging.getLogger("jobbot.sources")

_HEADERS = {
    "User-Agent": "jobbot/1.0 (+https://github.com/) personal job alerter",
    "Accept": "application/json",
}
_TIMEOUT = 25


def _get_json(url: str, params: dict | None = None):
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------------------------------- #
#  Remote-first free JSON APIs
# --------------------------------------------------------------------------- #
def fetch_remotive() -> list[Job]:
    data = _get_json("https://remotive.com/api/remote-jobs", {"limit": 200})
    jobs = []
    for j in data.get("jobs", []):
        jobs.append(
            Job(
                source="remotive",
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                url=j.get("url", ""),
                location=j.get("candidate_required_location", "") or "Remote",
                remote=True,
                tags=j.get("tags", []) or [],
                description=j.get("description", ""),
                posted_at=parse_date(j.get("publication_date")),
            )
        )
    return jobs


def fetch_arbeitnow() -> list[Job]:
    data = _get_json("https://www.arbeitnow.com/api/job-board-api")
    jobs = []
    for j in data.get("data", []):
        jobs.append(
            Job(
                source="arbeitnow",
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                url=j.get("url", ""),
                location=j.get("location", ""),
                remote=bool(j.get("remote")),
                tags=(j.get("tags", []) or []) + (j.get("job_types", []) or []),
                description=j.get("description", ""),
                posted_at=parse_date(j.get("created_at")),
            )
        )
    return jobs


def fetch_jobicy() -> list[Job]:
    data = _get_json("https://jobicy.com/api/v2/remote-jobs", {"count": 100})
    jobs = []
    for j in data.get("jobs", []):
        jobs.append(
            Job(
                source="jobicy",
                title=j.get("jobTitle", ""),
                company=j.get("companyName", ""),
                url=j.get("url", ""),
                location=j.get("jobGeo", "") or "Remote",
                remote=True,
                tags=(j.get("jobIndustry", []) or []) + (j.get("jobType", []) or []),
                description=j.get("jobExcerpt", "") or j.get("jobDescription", ""),
                posted_at=parse_date(j.get("pubDate")),
            )
        )
    return jobs


def fetch_remoteok() -> list[Job]:
    # RemoteOK returns a list whose FIRST element is a legal/metadata notice.
    data = _get_json("https://remoteok.com/api")
    jobs = []
    for j in data:
        if not isinstance(j, dict) or "position" not in j and "title" not in j:
            continue  # skip the leading metadata object
        jobs.append(
            Job(
                source="remoteok",
                title=j.get("position") or j.get("title", ""),
                company=j.get("company", ""),
                url=j.get("url") or j.get("apply_url", ""),
                location=j.get("location", "") or "Remote",
                remote=True,
                tags=j.get("tags", []) or [],
                description=j.get("description", ""),
                posted_at=parse_date(j.get("date")),
            )
        )
    return jobs


# --------------------------------------------------------------------------- #
#  Pakistan-local: Rozee.pk (HTML scrape — best effort)
# --------------------------------------------------------------------------- #
def fetch_rozee(queries: list[str] | None = None) -> list[Job]:
    from bs4 import BeautifulSoup  # imported lazily so API-only users needn't install it

    queries = queries or ["software engineer"]
    html_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    jobs: list[Job] = []
    seen_urls: set[str] = set()

    for query in queries:
        q = urllib.parse.quote(query)
        url = f"https://www.rozee.pk/job/jsearch/q/{q}"
        try:
            resp = requests.get(url, headers=html_headers, timeout=_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("rozee query %r failed: %s", query, exc)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        # Job cards on Rozee are anchor tags linking to /job/... detail pages.
        # We look for links whose text looks like a job title. Markup changes
        # over time, so this stays intentionally loose.
        for a in soup.select("a[href*='/job/']"):
            href = a.get("href", "")
            title = a.get_text(strip=True)
            if not title or len(title) < 4:
                continue
            if not href.startswith("http"):
                href = "https://www.rozee.pk" + href
            if "/jsearch/" in href or href in seen_urls:
                continue
            seen_urls.add(href)
            # Company/location often live in a nearby container.
            container = a.find_parent(["div", "li", "article"])
            context = container.get_text(" ", strip=True) if container else title
            jobs.append(
                Job(
                    source="rozee",
                    title=title,
                    company="",              # not reliably parseable from search page
                    url=href,
                    location="Pakistan",
                    remote=False,
                    tags=[],
                    description=context,
                )
            )
    return jobs


# --------------------------------------------------------------------------- #
#  Registry + orchestration
# --------------------------------------------------------------------------- #
FETCHERS: dict[str, Callable[..., list[Job]]] = {
    "remotive": fetch_remotive,
    "arbeitnow": fetch_arbeitnow,
    "jobicy": fetch_jobicy,
    "remoteok": fetch_remoteok,
    "rozee": fetch_rozee,
}


def collect(config: dict) -> list[Job]:
    """Run every enabled source, tolerating individual failures."""
    enabled = config.get("sources", {})
    all_jobs: list[Job] = []
    for name, fetcher in FETCHERS.items():
        if not enabled.get(name, False):
            continue
        try:
            if name == "rozee":
                jobs = fetcher(config.get("rozee_queries"))
            else:
                jobs = fetcher()
            log.info("%-10s -> %3d jobs", name, len(jobs))
            all_jobs.extend(jobs)
        except Exception as exc:  # noqa: BLE001 — one bad source must not kill the run
            log.warning("source %r failed: %s", name, exc)
    return all_jobs
