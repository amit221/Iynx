"""
Discover GitHub repositories via the GitHub Search API.
Supports star count, creation date, and optional language filters.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)


@dataclass
class RepoInfo:
    """Repository metadata from discovery."""

    owner: str
    name: str
    full_name: str
    clone_url: str
    stars: int
    language: str | None
    description: str | None
    default_branch: str
    created_at: datetime | None = None


def build_search_query(
    min_stars: int,
    max_age_days: int | None,
    language: str | None = None,
) -> str:
    """
    Build the `q` string for GET /search/repositories (no network).

    If max_age_days is None, no created: filter is added.
    """
    parts = [f"stars:>{min_stars}"]
    if max_age_days is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).date().isoformat()
        parts.append(f"created:>{cutoff}")
    if language:
        parts.append(f"language:{language}")
    return " ".join(parts)


def _parse_created_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _search_repositories_page(
    query: str,
    page: int,
    per_page: int,
    token: str | None,
) -> dict:
    url = "https://api.github.com/search/repositories"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(per_page, 100),
        "page": page,
    }
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            last_error = e
            logger.warning("GitHub API attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def _item_to_repo(item: dict) -> RepoInfo:
    return RepoInfo(
        owner=item["owner"]["login"],
        name=item["name"],
        full_name=item["full_name"],
        clone_url=item["clone_url"],
        stars=item["stargazers_count"],
        language=item.get("language"),
        description=item.get("description"),
        default_branch=item.get("default_branch", "main"),
        created_at=_parse_created_at(item.get("created_at")),
    )


def fetch_repo_candidates(
    *,
    token: str | None = None,
    pool_size: int = 50,
    min_stars: int = 50,
    max_age_days: int | None = 30,
    language: str | None = None,
    max_pages: int = 5,
    per_page: int = 30,
) -> list[RepoInfo]:
    """
    Fetch repository candidates from GitHub Search, paginating until pool_size or max_pages.

    pool_size caps how many items to return (before host-side filters like CONTRIBUTING).
    """
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("No GITHUB_TOKEN set; API rate limit is 60 req/hr unauthenticated")

    query = build_search_query(min_stars, max_age_days, language)
    repos: list[RepoInfo] = []
    for page in range(1, max_pages + 1):
        data = _search_repositories_page(query, page, per_page, token)
        items = data.get("items") or []
        if not items:
            break
        for item in items:
            repos.append(_item_to_repo(item))
            if len(repos) >= pool_size:
                return repos
    return repos


def fetch_trendy_repos(
    token: str | None = None,
    limit: int = 5,
    min_stars: int = 50,
    max_age_days: int | None = 30,
    language: str | None = None,
    max_pages: int = 5,
    per_page: int = 30,
) -> list[RepoInfo]:
    """
    Fetch repositories sorted by stars (proxy for trendy).

    Paginates until `limit` results are collected from the API (use fetch_repo_candidates
    with a larger pool_size when you will filter downstream).
    """
    return fetch_repo_candidates(
        token=token,
        pool_size=limit,
        min_stars=min_stars,
        max_age_days=max_age_days,
        language=language,
        max_pages=max_pages,
        per_page=per_page,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    repos = fetch_trendy_repos(limit=5)
    for r in repos:
        print(f"{r.full_name} ({r.stars} stars) - {r.language or 'N/A'}")
