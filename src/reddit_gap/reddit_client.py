"""Minimal Reddit JSON fetch (read-only; respect User-Agent and rate limits)."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "python:the-fixer-reddit-gap:0.1 (by /u/local-dev; contact: https://github.com)"
)


def get_user_agent() -> str:
    import os

    return (os.environ.get("REDDIT_USER_AGENT") or "").strip() or DEFAULT_USER_AGENT


def fetch_json(
    url: str,
    *,
    session: requests.Session | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    sess = session or requests.Session()
    headers = {
        "User-Agent": get_user_agent(),
        "Accept": "application/json",
    }
    last: Exception | None = None
    for attempt in range(3):
        try:
            resp = sess.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 429:
                wait = 2.0 * (attempt + 1)
                logger.warning("Reddit rate limit; sleeping %.1fs", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object")
            return data
        except (requests.RequestException, ValueError) as e:
            last = e
            logger.warning("fetch attempt %s failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    assert last is not None
    raise last


def fetch_subreddit_new(
    subreddit: str,
    *,
    limit: int = 100,
    after: str | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    sub = subreddit.strip().removeprefix("r/").removeprefix("/")
    if not sub:
        raise ValueError("subreddit must be non-empty")
    q = f"https://www.reddit.com/r/{sub}/new.json?limit={min(limit, 100)}&raw_json=1"
    if after:
        q += f"&after={after}"
    return fetch_json(q, session=session)


def fetch_subreddit_about(
    subreddit: str,
    *,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    sub = subreddit.strip().removeprefix("r/").removeprefix("/")
    if not sub:
        raise ValueError("subreddit must be non-empty")
    url = f"https://www.reddit.com/r/{sub}/about.json?raw_json=1"
    return fetch_json(url, session=session)
