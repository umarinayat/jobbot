"""Common job model shared across every source."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _clean(text: Optional[str]) -> str:
    """Strip HTML tags and collapse whitespace to plain, searchable text."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)          # drop HTML tags
    text = re.sub(r"&[a-z]+;", " ", text)          # drop HTML entities
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Job:
    """A normalized job posting from any source."""

    source: str
    title: str
    company: str
    url: str
    location: str = ""
    remote: bool = False
    tags: list[str] = field(default_factory=list)
    description: str = ""
    posted_at: Optional[datetime] = None

    # Filled in by the matcher.
    score: int = 0
    matched_skills: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = _clean(self.title)
        self.company = _clean(self.company)
        self.location = _clean(self.location)
        self.description = _clean(self.description)
        self.tags = [t.lower().strip() for t in self.tags if t]

    @property
    def uid(self) -> str:
        """Stable unique id used to remember which jobs we've already sent."""
        basis = f"{self.source}|{self.url}|{self.title}|{self.company}".lower()
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

    @property
    def haystack(self) -> str:
        """All text a matcher should search, lowercased."""
        return " ".join(
            [self.title, self.company, self.location, " ".join(self.tags), self.description]
        ).lower()

    def to_dict(self) -> dict:
        """JSON-serializable form used by the dashboard front end."""
        return {
            "title": self.title,
            "company": self.company,
            "url": self.url,
            "location": self.location or ("Remote" if self.remote else ""),
            "remote": self.remote,
            "source": self.source,
            "score": self.score,
            "matched_skills": self.matched_skills,
            "tags": self.tags,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "age_days": round(self.age_days, 1) if self.age_days is not None else None,
        }

    @property
    def age_days(self) -> Optional[float]:
        if not self.posted_at:
            return None
        now = datetime.now(timezone.utc)
        posted = self.posted_at
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        return (now - posted).total_seconds() / 86400.0


def parse_date(value) -> Optional[datetime]:
    """Best-effort parse of the many date formats these APIs return."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (ValueError, OSError):
            return None
    text = str(value).strip()
    # Try ISO 8601 first (handles the trailing 'Z').
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
