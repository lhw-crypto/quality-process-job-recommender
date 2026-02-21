from dataclasses import dataclass
from datetime import datetime


@dataclass
class JobPosting:
    title: str
    company: str
    location: str
    url: str
    source: str
    snippet: str
    fetched_at: str


@dataclass
class ScoredJob:
    posting: JobPosting
    score: float
    reasons: list[str]


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
