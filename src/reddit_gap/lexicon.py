"""
Versioned lexicons for pain-shaped tasks vs AI-discourse signals.

Patterns are matched case-insensitively on post title + body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LEXICON_VERSION = "1"

# Multi-word and specific phrases first (longer wins when counting distinct hits).
PAIN_PHRASES: tuple[str, ...] = (
    r"\btl;dr\b",
    r"\btldr\b",
    r"\beli5\b",
    r"\btoo long\b",
    r"\bin plain english\b",
    r"\bplain english\b",
    r"\bwhat does this (?:say|mean)\b",
    r"\bcan someone (?:explain|translate)\b",
    r"\bhelp me (?:understand|word|write|draft)\b",
    r"\bhow (?:do|should) i (?:word|phrase|say|write)\b",
    r"\brephrase\b",
    r"\bproofread\b",
    r"\bcover letter\b",
    r"\bresume\b",
    r"\bsummarize\b",
    r"\bsummarise\b",
    r"\bsummary\b",
    r"\boutline\b",
    r"\bbullet points\b",
    r"\bstudy guide\b",
    r"\borganize (?:this|my)\b",
    r"\bread(?:ing)? (?:this )?letter\b",
    r"\btranslate (?:this|the)\b",
)

# Single tokens / short (after phrases) — some overlap with common English; used with word boundaries.
PAIN_TOKENS: tuple[str, ...] = (
    r"\bsummarize\b",
    r"\bsummarise\b",
    r"\brewrite\b",
    r"\brephrase\b",
    r"\bproofread\b",
    r"\btemplate\b",
    r"\bscript\b",
    r"\beli5\b",
)

AI_PHRASES: tuple[str, ...] = (
    r"\bchatgpt\b",
    r"\bgpt-4\b",
    r"\bgpt4\b",
    r"\bgpt-3\b",
    r"\bclaude\b",
    r"\bopenai\b",
    r"\banthropic\b",
    r"\bgemini\b",
    r"\bcopilot\b",
    r"\bgithub copilot\b",
    r"\bmidjourney\b",
    r"\bstable diffusion\b",
    r"\bllm\b",
    r"\blarge language model\b",
    r"\bprompt engineering\b",
    r"\bmy prompt\b",
    r"\bthe prompt\b",
    r"\bperplexity\b",
    r"\bcharacter\.ai\b",
)

AI_TOKENS: tuple[str, ...] = (
    r"\bai (?:tool|model|generated|slop|art)\b",
    r"\bgenerative ai\b",
)

# Sidebar / rules: moderation stance (flags only).
NO_AI_MARKERS: tuple[str, ...] = (
    r"\bno ai\b",
    r"\bban(?:ned)?\s+ai\b",
    r"\bai[- ]generated\b.*\bnot allowed\b",
    r"\bdo not use chatgpt\b",
)

LIABILITY_MARKERS: tuple[str, ...] = (
    r"\bmedical advice\b",
    r"\bnot a (?:doctor|physician)\b",
    r"\blegal advice\b",
    r"\bnot a lawyer\b",
    r"\battorney[- ]client\b",
)


@dataclass(frozen=True)
class CompiledLexicon:
    pain: list[re.Pattern[str]]
    ai: list[re.Pattern[str]]
    no_ai: list[re.Pattern[str]]
    liability: list[re.Pattern[str]]


def _compile(patterns: tuple[str, ...]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def _dedupe_patterns(patterns: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return tuple(out)


def compile_lexicon() -> CompiledLexicon:
    pain = _compile(_dedupe_patterns(PAIN_PHRASES + PAIN_TOKENS))
    ai = _compile(_dedupe_patterns(AI_PHRASES + AI_TOKENS))
    no_ai = _compile(NO_AI_MARKERS)
    liability = _compile(LIABILITY_MARKERS)
    return CompiledLexicon(pain=pain, ai=ai, no_ai=no_ai, liability=liability)
