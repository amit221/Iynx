"""End-to-end: fetch listings, classify, aggregate."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from reddit_gap.aggregate import SubredditRollup, finalize_rollup, merge_count_maps
from reddit_gap.classify import classify_sidebar, merge_post_signals
from reddit_gap.lexicon import compile_lexicon
from reddit_gap.reddit_client import fetch_subreddit_about, fetch_subreddit_new

logger = logging.getLogger(__name__)


def _sleep_between_requests() -> None:
    try:
        sec = float(os.environ.get("REDDIT_GAP_SLEEP_SEC", "2.0"))
    except ValueError:
        sec = 2.0
    if sec > 0:
        time.sleep(sec)


def _parse_listing_posts(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    data = payload.get("data") or {}
    children = data.get("children") or []
    posts: list[dict[str, Any]] = []
    for ch in children:
        if not isinstance(ch, dict):
            continue
        if ch.get("kind") != "t3":
            continue
        inner = ch.get("data")
        if isinstance(inner, dict):
            posts.append(inner)
    after = data.get("after")
    if after is not None and not isinstance(after, str):
        after = str(after) if after else None
    return posts, after


def analyze_subreddit(
    subreddit: str,
    *,
    max_posts: int = 100,
    gap_k: float = 1.0,
    session: requests.Session | None = None,
) -> SubredditRollup:
    """
    Fetch new posts (up to max_posts), classify, optionally load sidebar for flags.
    """
    lex = compile_lexicon()
    sess = session or requests.Session()
    sub = subreddit.strip().removeprefix("r/").removeprefix("/")

    sidebar_flags: list[str] = []
    sidebar_reasons: list[str] = []
    subscribers: int | None = None

    try:
        about = fetch_subreddit_about(sub, session=sess)
        about_data = (about.get("data") or {}) if isinstance(about, dict) else {}
        if isinstance(about_data, dict):
            raw_sub = about_data.get("subscribers")
            if isinstance(raw_sub, int):
                subscribers = raw_sub
            desc = about_data.get("public_description") or about_data.get("description")
            if isinstance(desc, str):
                sidebar_flags, sidebar_reasons = classify_sidebar(desc, lex)
    except Exception as e:
        logger.warning("about fetch failed for r/%s: %s", sub, e)

    _sleep_between_requests()

    collected: list[dict[str, Any]] = []
    after: str | None = None
    while len(collected) < max_posts:
        page_limit = min(100, max_posts - len(collected))
        try:
            payload = fetch_subreddit_new(sub, limit=page_limit, after=after, session=sess)
        except Exception as e:
            return SubredditRollup(
                subreddit=sub,
                n_posts=0,
                error=str(e),
                flags=["fetch_error"],
                sidebar_flags=sidebar_flags,
                sidebar_flag_reasons=sidebar_reasons,
            )

        posts, after = _parse_listing_posts(payload)
        if not posts:
            break
        collected.extend(posts)
        if not after or len(collected) >= max_posts:
            break
        _sleep_between_requests()

    collected = collected[:max_posts]

    pain_posts = 0
    ai_posts = 0
    both_posts = 0
    pain_maps: list[dict[str, int]] = []
    ai_maps: list[dict[str, int]] = []

    for p in collected:
        title = p.get("title") if isinstance(p.get("title"), str) else ""
        selftext = p.get("selftext") if isinstance(p.get("selftext"), str) else ""
        sig = merge_post_signals(title, selftext, lex)
        if sig.pain:
            pain_posts += 1
        if sig.ai:
            ai_posts += 1
        if sig.pain and sig.ai:
            both_posts += 1
        if sig.pain_hit_counts:
            pain_maps.append(sig.pain_hit_counts)
        if sig.ai_hit_counts:
            ai_maps.append(sig.ai_hit_counts)

    pain_tot = merge_count_maps(pain_maps)
    ai_tot = merge_count_maps(ai_maps)

    return finalize_rollup(
        sub,
        n_posts=len(collected),
        pain_posts=pain_posts,
        ai_posts=ai_posts,
        both_posts=both_posts,
        pain_hit_totals=pain_tot,
        ai_hit_totals=ai_tot,
        sidebar_flags=sidebar_flags,
        sidebar_reasons=sidebar_reasons,
        subscribers=subscribers,
        k=gap_k,
    )


def load_seed_subs(path: str) -> list[str]:
    out: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            out.append(s)
    return out
