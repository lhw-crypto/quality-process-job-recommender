from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .profile import load_profile
from .sources import collect_jobs
from .scoring import score_jobs
from .notify import send_email


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


def run(limit: int = 20) -> None:
    profile = load_profile()
    queries = profile["sources"]["keyword_queries"]
    per_source_limit = int(profile["sources"].get("per_source_limit", 80))

    jobs = collect_jobs(queries, per_source_limit)
    ranked = score_jobs(jobs, profile)

    threshold = float(profile["scoring"].get("preferred_threshold", 45))
    selected = [x for x in ranked if x.score >= threshold][:limit]

    # If strict threshold returns nothing, keep top-N candidates for daily review.
    used_fallback = False
    if not selected:
        selected = ranked[:limit]
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
        f"- Recommended (score >= {threshold}): {len([x for x in ranked if x.score >= threshold])}",
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

    email_subject = f"[Daily Job Match] 추천 {len(selected)}건 / 수집 {len(jobs)}건"
    preview = "\n".join(lines[: min(80, len(lines))])
    send_email(email_subject, preview)
