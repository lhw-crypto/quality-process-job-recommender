from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .profile import load_profile
from .sources import collect_jobs
from .scoring import score_jobs

STATE_PATH = Path("data/sent_jobs.json")
FOUR_YEAR_REQUIRED_MARKERS = [
    "4년제",
    "대졸",
    "학사",
    "대학교 졸업",
    "bachelor",
    "bachelors",
    "bachelor's",
    "bs ",
    "b.s",
    "ba ",
    "master",
    "석사",
    "박사",
]
EXCLUDED_EDU_MARKERS = [
    "2년제",
    "3년제",
    "전문대",
    "초대졸",
    "고졸",
    "학력무관",
]


def _to_dict(item):
    return {
        "score": item.score,
        "source": item.posting.source,
        "title": item.posting.title,
        "company": item.posting.company,
        "location": item.posting.location,
        "url": item.posting.url,
        "snippet": item.posting.snippet,
        "reasons": item.reasons,
        "fetched_at": item.posting.fetched_at,
    }


def _load_sent_urls() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return set()
    urls = data.get("sent_urls", [])
    return {u for u in urls if isinstance(u, str) and u.strip()}


def _save_sent_urls(urls: set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sent_urls": sorted(urls),
    }
    STATE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _is_four_year_plus_job(posting) -> bool:
    text = " ".join(
        [
            posting.title or "",
            posting.snippet or "",
            posting.url or "",
        ]
    ).lower()
    if any(marker in text for marker in EXCLUDED_EDU_MARKERS):
        return False
    return any(marker in text for marker in FOUR_YEAR_REQUIRED_MARKERS)


def run(limit: int = 20) -> None:
    profile = load_profile()
    queries = profile["sources"]["keyword_queries"]
    per_source_limit = int(profile["sources"].get("per_source_limit", 80))

    jobs = collect_jobs(queries, per_source_limit)
    edu_filtered_jobs = [x for x in jobs if _is_four_year_plus_job(x)]
    ranked = score_jobs(edu_filtered_jobs, profile)
    sent_urls = _load_sent_urls()
    ranked_unsent = [x for x in ranked if x.posting.url not in sent_urls]

    threshold = float(profile["scoring"].get("preferred_threshold", 45))
    selected = [x for x in ranked_unsent if x.score >= threshold][:limit]

    # If strict threshold returns nothing, keep top-N candidates for daily review.
    used_fallback = False
    if not selected:
        selected = ranked_unsent[:limit]
        used_fallback = True

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"recommendations_{timestamp}.json"
    latest_path = output_dir / "latest.json"
    md_path = output_dir / f"recommendations_{timestamp}.md"
    latest_md_path = output_dir / "latest.md"

    payload = {
        "generated_at_utc": timestamp,
        "total_collected": len(jobs),
        "after_education_filter": len(edu_filtered_jobs),
        "after_dedup_filter": len(ranked_unsent),
        "total_recommended": len(selected),
        "used_fallback_top_n": used_fallback,
        "items": [_to_dict(x) for x in selected],
    }

    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    latest_path.write_text(json_text, encoding="utf-8")

    lines = [
        f"# Daily Quality/Process Job Recommendations ({timestamp} UTC)",
        "",
        f"- Collected: {len(jobs)}",
        f"- 4-year filter passed: {len(edu_filtered_jobs)}",
        f"- Not sent before: {len(ranked_unsent)}",
        f"- Recommended (score >= {threshold}): {len([x for x in ranked_unsent if x.score >= threshold])}",
        f"- Fallback Used: {used_fallback}",
        "",
    ]

    for idx, item in enumerate(selected, start=1):
        lines += [
            f"## {idx}. [{item.posting.title}]({item.posting.url})",
            f"- Score: {item.score}",
            f"- Source: {item.posting.source}",
            f"- Company: {item.posting.company or '-'}",
            f"- Location: {item.posting.location or '-'}",
            f"- Why: {' | '.join(item.reasons)}",
            "",
        ]

    md_text = "\n".join(lines)
    md_path.write_text(md_text, encoding="utf-8")
    latest_md_path.write_text(md_text, encoding="utf-8")
