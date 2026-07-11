#!/usr/bin/env python3
"""JobBot entry point.

Usage:
    python main.py               # full run: fetch, match, email new jobs, save state
    python main.py --dry-run     # fetch + match, print results, DO NOT email or save
    python main.py --self-test   # offline: run mock jobs through the pipeline (no network)
    python main.py --preview out.html   # also write the email HTML to a file

Environment variables (for the real run / GitHub Actions secrets):
    EMAIL_ADDRESS        your sending address (e.g. you@gmail.com)
    EMAIL_APP_PASSWORD   a Gmail App Password (NOT your normal password)
    EMAIL_TO             where alerts go (defaults to EMAIL_ADDRESS)
    SMTP_HOST/SMTP_PORT  optional; default smtp.gmail.com:465
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from jobbot import dashboard, matcher, notifier, sources, state
from jobbot.models import Job

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
)
log = logging.getLogger("jobbot")


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _print_jobs(jobs: list[Job]) -> None:
    if not jobs:
        print("\n(no matching jobs)\n")
        return
    print(f"\n===== {len(jobs)} matching jobs =====")
    for j in jobs:
        skills = ", ".join(j.matched_skills)
        print(f"[{j.score:>2}] {j.title}  —  {j.company or '?'} ({j.source})")
        print(f"      {j.location or 'Remote'} | skills: {skills}")
        print(f"      {j.url}")
    print()


def _mock_jobs() -> list[Job]:
    """Representative sample used by --self-test (no network needed)."""
    return [
        Job(
            source="remotive",
            title="Senior Full Stack Engineer (React / Node)",
            company="Acme Remote",
            url="https://example.com/job/1",
            location="Worldwide",
            remote=True,
            tags=["react", "node", "typescript"],
            description="Build products with React, Node.js, TypeScript and Python. Remote.",
            posted_at=datetime.now(timezone.utc),
        ),
        Job(
            source="arbeitnow",
            title="Python Backend Developer (LLM / LangChain)",
            company="AI Labs",
            url="https://example.com/job/2",
            location="Remote",
            remote=True,
            tags=["python", "flask", "ai"],
            description="Work on LLM features with Python, Flask, LangChain and RAG pipelines.",
            posted_at=datetime.now(timezone.utc),
        ),
        Job(
            source="arbeitnow",
            title="Senior Salesforce Administrator",
            company="CRM Corp",
            url="https://example.com/job/3",
            location="Berlin",
            remote=False,
            tags=["salesforce"],
            description="Administer Salesforce. On-site in Berlin.",
            posted_at=datetime.now(timezone.utc),
        ),
        Job(
            source="rozee",
            title="MERN Stack Developer",
            company="Lahore Tech",
            url="https://example.com/job/4",
            location="Lahore, Pakistan",
            remote=False,
            tags=[],
            description="React, Node.js, Express, MongoDB developer needed in Lahore.",
            posted_at=datetime.now(timezone.utc),
        ),
    ]


def run(config: dict, *, dry_run: bool, preview: Path | None, self_test: bool) -> int:
    if self_test:
        raw = _mock_jobs()
        log.info("self-test: %d mock jobs", len(raw))
    else:
        raw = sources.collect(config)
        log.info("collected %d raw jobs from all sources", len(raw))

    matched = matcher.match(raw, config)

    # Always refresh the dashboard data (the static site reads this file).
    dashboard.write_data(matched)

    seen = state.load()
    fresh = state.filter_new(matched, seen)
    log.info("%d matched, %d are new since last run", len(matched), len(fresh))

    if preview and matched:
        preview.write_text(notifier.render_html(matched), encoding="utf-8")
        log.info("wrote HTML preview -> %s", preview)

    if dry_run or self_test:
        _print_jobs(matched)
        print("Dry run: no email sent, state not modified.")
        return 0

    if fresh:
        notifier.send_email(fresh)
    else:
        log.info("no new jobs to email")

    state.save(fresh, seen)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="JobBot — free job alerter")
    parser.add_argument("--config", default="config.yaml", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="fetch+match, no email/state")
    parser.add_argument("--self-test", action="store_true", help="offline pipeline test")
    parser.add_argument("--preview", type=Path, help="write email HTML to this file")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    return run(config, dry_run=args.dry_run, preview=args.preview, self_test=args.self_test)


if __name__ == "__main__":
    sys.exit(main())
