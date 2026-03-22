"""Roll up per-post signals into subreddit-level indices and gap score."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from reddit_gap.lexicon import LEXICON_VERSION


def _per_1k(count: int, n_posts: int) -> float:
    if n_posts <= 0:
        return 0.0
    return (count / n_posts) * 1000.0


def _top_keys(counts: dict[str, int], limit: int = 8) -> list[dict[str, Any]]:
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    out: list[dict[str, Any]] = []
    for key, n in items[:limit]:
        out.append({"pattern": key, "count": n})
    return out


@dataclass
class SubredditRollup:
    """Serializable result for one subreddit."""

    subreddit: str
    lexicon_version: str = LEXICON_VERSION
    # Ingestion
    n_posts: int = 0
    subscribers: int | None = None
    fetched_at: str = ""
    # Rates (posts with >=1 hit / total)
    pain_posts: int = 0
    ai_posts: int = 0
    both_posts: int = 0
    pain_index: float = 0.0
    ai_penetration_index: float = 0.0
    gap_score: float = 0.0
    gap_k: float = 1.0
    # Flags
    flags: list[str] = field(default_factory=list)
    sidebar_flags: list[str] = field(default_factory=list)
    sidebar_flag_reasons: list[str] = field(default_factory=list)
    # Evidence
    pain_hit_totals: dict[str, int] = field(default_factory=dict)
    ai_hit_totals: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence"] = {
            "top_pain_patterns": _top_keys(self.pain_hit_totals),
            "top_ai_patterns": _top_keys(self.ai_hit_totals),
        }
        return d


def compute_gap_score(
    pain_posts: int,
    ai_posts: int,
    n_posts: int,
    k: float = 1.0,
) -> tuple[float, float, float]:
    """Return (pain_index, ai_penetration_index, gap_score) per 1k posts scale."""
    pain_index = _per_1k(pain_posts, n_posts)
    ai_pen = _per_1k(ai_posts, n_posts)
    gap = pain_index - k * ai_pen
    return pain_index, ai_pen, gap


def finalize_rollup(
    sub: str,
    n_posts: int,
    pain_posts: int,
    ai_posts: int,
    both_posts: int,
    pain_hit_totals: dict[str, int],
    ai_hit_totals: dict[str, int],
    sidebar_flags: list[str],
    sidebar_reasons: list[str],
    subscribers: int | None,
    k: float = 1.0,
    low_sample_threshold: int = 20,
) -> SubredditRollup:
    pain_i, ai_i, gap = compute_gap_score(pain_posts, ai_posts, n_posts, k=k)
    flags: list[str] = []
    if n_posts < low_sample_threshold:
        flags.append("low_sample")
    flags.extend(sidebar_flags)

    return SubredditRollup(
        subreddit=sub,
        n_posts=n_posts,
        subscribers=subscribers,
        fetched_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        pain_posts=pain_posts,
        ai_posts=ai_posts,
        both_posts=both_posts,
        pain_index=round(pain_i, 3),
        ai_penetration_index=round(ai_i, 3),
        gap_score=round(gap, 3),
        gap_k=k,
        flags=sorted(set(flags)),
        sidebar_flags=sidebar_flags,
        sidebar_flag_reasons=sidebar_reasons,
        pain_hit_totals=dict(pain_hit_totals),
        ai_hit_totals=dict(ai_hit_totals),
    )


def merge_count_maps(maps: list[dict[str, int]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in maps:
        for key, v in m.items():
            out[key] = out.get(key, 0) + v
    return out
