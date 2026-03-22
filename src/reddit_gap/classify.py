"""Apply compiled lexicons to post text and subreddit metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from reddit_gap.lexicon import CompiledLexicon


@dataclass
class PostSignals:
    """Per-submission classification."""

    pain: bool
    ai: bool
    pain_hit_counts: dict[str, int] = field(default_factory=dict)
    ai_hit_counts: dict[str, int] = field(default_factory=dict)


def _pattern_key(pat: re.Pattern[str], prefix: str, index: int) -> str:
    return f"{prefix}:{index}:{pat.pattern[:80]}"


def classify_text(text: str, lex: CompiledLexicon) -> PostSignals:
    """Classify a single blob (e.g. title + selftext)."""
    if not text or not text.strip():
        return PostSignals(pain=False, ai=False)

    pain_hit_counts: dict[str, int] = {}
    for i, pat in enumerate(lex.pain):
        if pat.search(text):
            key = _pattern_key(pat, "pain", i)
            pain_hit_counts[key] = pain_hit_counts.get(key, 0) + 1

    ai_hit_counts: dict[str, int] = {}
    for i, pat in enumerate(lex.ai):
        if pat.search(text):
            key = _pattern_key(pat, "ai", i)
            ai_hit_counts[key] = ai_hit_counts.get(key, 0) + 1

    return PostSignals(
        pain=bool(pain_hit_counts),
        ai=bool(ai_hit_counts),
        pain_hit_counts=pain_hit_counts,
        ai_hit_counts=ai_hit_counts,
    )


def merge_post_signals(title: str, selftext: str | None, lex: CompiledLexicon) -> PostSignals:
    """Merge title + body; one scan over combined text."""
    parts = [title or ""]
    if selftext:
        parts.append(selftext)
    combined = "\n".join(parts)
    return classify_text(combined, lex)


def classify_sidebar(description: str | None, lex: CompiledLexicon) -> tuple[list[str], list[str]]:
    """
    Return (flags, flag_reasons) from public description / rules text.
    flags: no_ai_policy, liability_heavy
    """
    text = description or ""
    flags: list[str] = []
    reasons: list[str] = []
    if not text.strip():
        return flags, reasons

    for pat in lex.no_ai:
        if pat.search(text):
            if "no_ai_policy" not in flags:
                flags.append("no_ai_policy")
                reasons.append(f"sidebar:no_ai:{pat.pattern[:48]}")

    for pat in lex.liability:
        if pat.search(text):
            if "liability_heavy" not in flags:
                flags.append("liability_heavy")
                reasons.append(f"sidebar:liability:{pat.pattern[:48]}")

    return flags, reasons
