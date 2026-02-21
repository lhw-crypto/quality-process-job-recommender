from __future__ import annotations

from urllib.parse import quote_plus
import re
import requests
from bs4 import BeautifulSoup

from .models import JobPosting, now_iso

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
TIMEOUT = 18
ROLE_HINTS = ["품질", "quality", "qa", "qc", "공정", "process", "engineer", "manufacturing"]


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _safe_get(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.text


def _extract_links_generic(html: str, base_url: str, source_name: str, limit: int) -> list[JobPosting]:
    soup = BeautifulSoup(html, "html.parser")
    postings: list[JobPosting] = []
    seen: set[str] = set()

    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue

        text = _clean_text(a.get_text(" ", strip=True))
        if len(text) < 4:
            continue
        if not any(k in text.lower() for k in ROLE_HINTS):
            continue

        if href.startswith("/"):
            url = base_url.rstrip("/") + href
        elif href.startswith("http"):
            url = href
        else:
            url = base_url.rstrip("/") + "/" + href

        if url in seen:
            continue
        seen.add(url)

        postings.append(
            JobPosting(
                title=text,
                company="",
                location="",
                url=url,
                source=source_name,
                snippet=text,
                fetched_at=now_iso(),
            )
        )
        if len(postings) >= limit:
            break

    return postings


def _contains_query(text: str, query: str) -> bool:
    q_tokens = [x for x in re.split(r"\s+", query.lower()) if x]
    hay = (text or "").lower()
    return any(tok in hay for tok in q_tokens)


def fetch_wanted_jobs(query: str, limit: int) -> list[JobPosting]:
    url = f"https://www.wanted.co.kr/search?query={quote_plus(query)}&tab=position"
    return _extract_links_generic(_safe_get(url), "https://www.wanted.co.kr", "wanted", limit)


def fetch_jobkorea_jobs(query: str, limit: int) -> list[JobPosting]:
    url = f"https://www.jobkorea.co.kr/Search/?stext={quote_plus(query)}"
    return _extract_links_generic(_safe_get(url), "https://www.jobkorea.co.kr", "jobkorea", limit)


def fetch_saramin_jobs(query: str, limit: int) -> list[JobPosting]:
    url = f"https://www.saramin.co.kr/zf_user/search?searchword={quote_plus(query)}"
    return _extract_links_generic(_safe_get(url), "https://www.saramin.co.kr", "saramin", limit)


def fetch_linkedin_jobs(query: str, limit: int) -> list[JobPosting]:
    url = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(query)}"
    return _extract_links_generic(_safe_get(url), "https://www.linkedin.com", "linkedin", limit)


def fetch_remoteok_jobs(query: str, limit: int) -> list[JobPosting]:
    url = f"https://remoteok.com/remote-{quote_plus(query)}-jobs"
    return _extract_links_generic(_safe_get(url), "https://remoteok.com", "remoteok", limit)


def fetch_remotive_api(query: str, limit: int) -> list[JobPosting]:
    url = "https://remotive.com/api/remote-jobs"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    out: list[JobPosting] = []

    for item in data.get("jobs", []):
        title = _clean_text(item.get("title", ""))
        company = _clean_text(item.get("company_name", ""))
        location = _clean_text(item.get("candidate_required_location", ""))
        snippet = _clean_text(item.get("description", ""))
        hay = f"{title} {company} {location} {snippet}"
        if not _contains_query(hay, query):
            continue
        out.append(
            JobPosting(
                title=title,
                company=company,
                location=location,
                url=item.get("url", ""),
                source="remotive",
                snippet=snippet[:400],
                fetched_at=now_iso(),
            )
        )
        if len(out) >= limit:
            break

    return out


def fetch_arbeitnow_api(query: str, limit: int) -> list[JobPosting]:
    url = "https://www.arbeitnow.com/api/job-board-api"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    out: list[JobPosting] = []

    for item in data.get("data", []):
        title = _clean_text(item.get("title", ""))
        company = _clean_text(item.get("company_name", ""))
        location = _clean_text(item.get("location", ""))
        tags = " ".join(item.get("tags", []))
        snippet = _clean_text(tags)
        hay = f"{title} {company} {location} {tags}"
        if not _contains_query(hay, query):
            continue
        out.append(
            JobPosting(
                title=title,
                company=company,
                location=location,
                url=item.get("url", ""),
                source="arbeitnow",
                snippet=snippet[:400],
                fetched_at=now_iso(),
            )
        )
        if len(out) >= limit:
            break

    return out


def collect_jobs(queries: list[str], per_source_limit: int) -> list[JobPosting]:
    source_functions = [
        fetch_wanted_jobs,
        fetch_jobkorea_jobs,
        fetch_saramin_jobs,
        fetch_linkedin_jobs,
        fetch_remoteok_jobs,
        fetch_remotive_api,
        fetch_arbeitnow_api,
    ]

    all_jobs: list[JobPosting] = []
    seen: set[str] = set()

    for query in queries:
        for fn in source_functions:
            try:
                jobs = fn(query, per_source_limit)
            except Exception:
                continue

            for job in jobs:
                if not job.url or job.url in seen:
                    continue
                seen.add(job.url)
                all_jobs.append(job)

    return all_jobs