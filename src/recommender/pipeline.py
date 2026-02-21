from __future__ import annotations

import json
from datetime import datetime
from html import escape
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


def _build_text_email(
    timestamp: str,
    collected: int,
    recommended_over_threshold: int,
    used_fallback: bool,
    selected,
) -> str:
    lines = [
        f"Daily Quality/Process Job Recommendations ({timestamp} UTC)",
        "",
        f"Collected: {collected}",
        f"Recommended (score threshold): {recommended_over_threshold}",
        f"Fallback Used: {used_fallback}",
        "",
    ]
    for idx, item in enumerate(selected, start=1):
        lines.extend(
            [
                f"{idx}. {item.posting.title}",
                f"Score: {item.score}",
                f"Source: {item.posting.source}",
                f"Company: {item.posting.company or '-'}",
                f"Location: {item.posting.location or '-'}",
                f"Why: {' | '.join(item.reasons)}",
                f"URL: {item.posting.url}",
                "",
            ]
        )
    return "\n".join(lines)


def _build_html_email(
    timestamp: str,
    collected: int,
    recommended_over_threshold: int,
    used_fallback: bool,
    selected,
) -> str:
    cards = []
    for idx, item in enumerate(selected, start=1):
        reasons = "".join(f"<li>{escape(reason)}</li>" for reason in item.reasons[:4])
        cards.append(
            f"""
            <tr>
              <td style="padding:0 0 14px 0;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #d9e2ec;border-radius:12px;background:#ffffff;">
                  <tr>
                    <td style="padding:16px 18px;">
                      <div style="font-size:12px;color:#486581;margin-bottom:6px;">#{idx} | {escape(item.posting.source)}</div>
                      <div style="font-size:17px;line-height:1.35;font-weight:700;color:#102a43;margin-bottom:8px;">{escape(item.posting.title)}</div>
                      <div style="font-size:13px;color:#334e68;margin-bottom:10px;">Company: {escape(item.posting.company or '-')} | Location: {escape(item.posting.location or '-')}</div>
                      <div style="display:inline-block;background:#0b7285;color:#ffffff;padding:5px 10px;border-radius:999px;font-size:12px;font-weight:700;margin-bottom:10px;">Match Score {item.score}</div>
                      <ul style="margin:8px 0 12px 18px;padding:0;color:#334e68;font-size:13px;line-height:1.45;">{reasons}</ul>
                      <a href="{escape(item.posting.url)}" style="display:inline-block;background:#1971c2;color:#ffffff;text-decoration:none;padding:9px 13px;border-radius:8px;font-size:13px;font-weight:700;">공고 바로보기</a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            """
        )

    return f"""
    <!doctype html>
    <html lang="ko">
      <body style="margin:0;padding:0;background:#f4f7fb;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fb;padding:24px 10px;">
          <tr>
            <td align="center">
              <table role="presentation" width="760" cellpadding="0" cellspacing="0" style="max-width:760px;width:100%;background:#ffffff;border:1px solid #d9e2ec;border-radius:14px;">
                <tr>
                  <td style="padding:22px 24px;background:linear-gradient(135deg,#0b7285,#1971c2);color:#ffffff;border-radius:14px 14px 0 0;">
                    <div style="font-size:22px;font-weight:800;letter-spacing:0.2px;">Daily Quality/Process Job Match</div>
                    <div style="font-size:13px;opacity:0.95;margin-top:6px;">Generated at {escape(timestamp)} UTC</div>
                  </td>
                </tr>
                <tr>
                  <td style="padding:18px 24px 8px 24px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;border:1px solid #d9e2ec;border-radius:10px;">
                      <tr>
                        <td style="padding:12px 14px;font-size:13px;color:#243b53;">
                          <strong>Collected:</strong> {collected} &nbsp;|&nbsp;
                          <strong>Recommended:</strong> {len(selected)} &nbsp;|&nbsp;
                          <strong>Threshold Hits:</strong> {recommended_over_threshold} &nbsp;|&nbsp;
                          <strong>Fallback:</strong> {used_fallback}
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:14px 24px 24px 24px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                      {''.join(cards)}
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


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

    recommended_over_threshold = len([x for x in ranked if x.score >= threshold])
    email_subject = f"[Daily Job Match] 추천 {len(selected)}건 / 수집 {len(jobs)}건"
    text_body = _build_text_email(
        timestamp=timestamp,
        collected=len(jobs),
        recommended_over_threshold=recommended_over_threshold,
        used_fallback=used_fallback,
        selected=selected,
    )
    html_body = _build_html_email(
        timestamp=timestamp,
        collected=len(jobs),
        recommended_over_threshold=recommended_over_threshold,
        used_fallback=used_fallback,
        selected=selected,
    )
    send_email(email_subject, text_body, html_body)
