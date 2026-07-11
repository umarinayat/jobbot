"""Remembers which jobs have already been sent so you're only alerted once."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .models import Job

log = logging.getLogger("jobbot.state")

DEFAULT_PATH = Path("data/seen_jobs.json")
# Forget jobs after this many days so the file doesn't grow forever.
_RETENTION_SECONDS = 60 * 24 * 3600


def load(path: Path = DEFAULT_PATH) -> dict[str, float]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("could not read state file (%s); starting fresh", exc)
        return {}


def filter_new(jobs: list[Job], seen: dict[str, float]) -> list[Job]:
    """Return only jobs whose uid we have not recorded before."""
    return [j for j in jobs if j.uid not in seen]


def save(new_jobs: list[Job], seen: dict[str, float], path: Path = DEFAULT_PATH) -> None:
    now = time.time()
    for job in new_jobs:
        seen[job.uid] = now
    # Prune anything older than the retention window.
    seen = {uid: ts for uid, ts in seen.items() if now - ts < _RETENTION_SECONDS}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(seen, indent=0), encoding="utf-8")
    log.info("state saved: %d remembered jobs", len(seen))
