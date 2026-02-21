from __future__ import annotations

import re

from .models import JobPosting, ScoredJob


def _tokenize(text: str) -> set[str]:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9가-힣\s\-/+]", " ", text)
    return {t for t in text.split() if t}


def _score_keyword_group(text_tokens: set[str], keywords: list[str], points_per_hit: float) -> tuple[float, list[str]]:
    hits: list[str] = []
    for kw in keywords:
        kw_tokens = _tokenize(kw)
        if kw_tokens and kw_tokens.issubset(text_tokens):
            hits.append(kw)
    return min(100.0, len(hits) * points_per_hit), hits


def score_jobs(jobs: list[JobPosting], profile: dict) -> list[ScoredJob]:
    p = profile["profile"]
    weights = profile["scoring"]
    scored: list[ScoredJob] = []

    for job in jobs:
        text = " ".join([
            job.title or "",
            job.company or "",
            job.location or "",
            job.snippet or "",
            job.url or "",
            job.source or "",
        ])
        tokens = _tokenize(text)

        role_score, role_hits = _score_keyword_group(tokens, p["role_keywords"], points_per_hit=16.0)
        industry_score, industry_hits = _score_keyword_group(tokens, p["industry_keywords"], points_per_hit=22.0)
        skill_score, skill_hits = _score_keyword_group(tokens, p["skill_keywords"], points_per_hit=18.0)
        seniority_score, seniority_hits = _score_keyword_group(tokens, p["seniority_keywords"], points_per_hit=25.0)

        seniority_boost = 8.0 if any(k in tokens for k in ["경력", "experience", "mid", "junior", "entry", "associate"]) else 0.0
        final_score = (
            role_score * weights["role_weight"]
            + industry_score * weights["industry_weight"]
            + skill_score * weights["skill_weight"]
            + min(100.0, seniority_score + seniority_boost) * weights["seniority_weight"]
        )

        reasons: list[str] = []
        if role_hits:
            reasons.append("직무 키워드 일치: " + ", ".join(role_hits[:5]))
        if industry_hits:
            reasons.append("산업 키워드 일치: " + ", ".join(industry_hits[:4]))
        if skill_hits:
            reasons.append("스킬 키워드 일치: " + ", ".join(skill_hits[:5]))
        if seniority_hits:
            reasons.append("연차/레벨 신호 일치: " + ", ".join(seniority_hits[:4]))
        if not reasons:
            reasons.append("핵심 키워드 일치가 적어 낮은 점수")

        scored.append(ScoredJob(posting=job, score=round(final_score, 2), reasons=reasons))

    return sorted(scored, key=lambda x: x.score, reverse=True)
