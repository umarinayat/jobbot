"""Writes the JSON that the static GitHub Pages dashboard reads."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .models import Job

log = logging.getLogger("jobbot.dashboard")

DEFAULT_PATH = Path("docs/jobs.json")


def write_data(jobs: list[Job], path: Path = DEFAULT_PATH) -> None:
    """Serialize the current matched jobs for the front end to render."""
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(jobs),
        "jobs": [j.to_dict() for j in jobs],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    log.info("dashboard data written -> %s (%d jobs)", path, len(jobs))
