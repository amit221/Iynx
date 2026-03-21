"""
Discover GitHub repositories via the GitHub Search API.

Repository search: star count, creation date, language.
Issue search: repos that have at least one open issue (any label) in a given language.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Sequence
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
    language: str | Sequence[str] | None = None,
) -> str:
    """
    Build the `q` string for GET /search/repositories (no network).

    If max_age_days is None, no created: filter is added.
    `language` may be one slug or several; multiple values become a GitHub OR group, e.g.
    (language:javascript OR language:typescript).
    """
    parts = [f"stars:>{min_stars}"]
    if max_age_days is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).date().isoformat()
        parts.append(f"created:>{cutoff}")
    if language:
        if isinstance(language, str):
            parts.append(f"language:{language}")
        else:
            langs = [s.strip() for s in language if isinstance(s, str) and s.strip()]
            if len(langs) == 1:
                parts.append(f"language:{langs[0]}")
            elif len(langs) > 1:
                parts.append("(" + " OR ".join(f"language:{lg}" for lg in langs) + ")")
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


def build_open_issues_search_query(language: str) -> str:
    """
    Build the `q` string for GET /search/issues (no network).

    Matches open GitHub issues only (`is:issue` excludes pull requests). No label
    filters — not limited to good-first-issue or help-wanted.
    """
    lang = language.strip()
    if not lang:
        raise ValueError("language must be non-empty")
    return f"is:issue is:open language:{lang}"


def _owner_repo_from_repository_url(url: str | None) -> tuple[str, str] | None:
    """Parse owner/name from an issue's repository_url (api.github.com/repos/...)."""
    if not url or not isinstance(url, str):
        return None
    prefix = "https://api.github.com/repos/"
    if not url.startswith(prefix):
        return None
    rest = url[len(prefix) :].strip("/")
    if "/" not in rest:
        return None
    owner, name = rest.split("/", 1)
    owner, name = owner.strip(), name.strip()
    if not owner or not name or "/" in name:
        return None
    return owner, name


def _search_issues_page(
    query: str,
    page: int,
    per_page: int,
    token: str | None,
) -> dict:
    url = "https://api.github.com/search/issues"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    params = {
        "q": query,
        "sort": "updated",
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
            logger.warning("GitHub issues search attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def fetch_repos_with_open_issues(
    *,
    token: str | None = None,
    pool_size: int = 50,
    languages: Sequence[str] = ("javascript", "typescript", "python"),
    max_pages: int = 5,
    per_page: int = 30,
) -> list[RepoInfo]:
    """
    Discover repos by searching for open issues (not PRs) in each language.

    Uses one issue-search query per language per page (avoids tight GitHub search
    operator limits). Does not filter by good-first-issue or other labels.
    Hydrates each unique repo via GET /repos/{owner}/{name} for clone URL and default branch.
    """
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("No GITHUB_TOKEN set; API rate limit is 60 req/hr unauthenticated")

    seen_full: set[str] = set()
    ordered_pairs: list[tuple[str, str]] = []

    for page in range(1, max_pages + 1):
        for lang in languages:
            if len(ordered_pairs) >= pool_size:
                break
            query = build_open_issues_search_query(lang)
            data = _search_issues_page(query, page, per_page, token)
            items = data.get("items") or []
            for item in items:
                pair = _owner_repo_from_repository_url(item.get("repository_url"))
                if pair is None:
                    continue
                owner, name = pair
                full = f"{owner}/{name}"
                if full in seen_full:
                    continue
                seen_full.add(full)
                ordered_pairs.append((owner, name))
                if len(ordered_pairs) >= pool_size:
                    break
        if len(ordered_pairs) >= pool_size:
            break

    out: list[RepoInfo] = []
    for owner, name in ordered_pairs[:pool_size]:
        info = fetch_repo_by_full_name(owner, name, token=token)
        if info is not None:
            out.append(info)
    return out


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
    language: str | Sequence[str] | None = None,
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


def fetch_repo_by_full_name(
    owner: str,
    name: str,
    *,
    token: str | None = None,
) -> RepoInfo | None:
    """
    Fetch a single repository via GET /repos/{owner}/{name}.

    Returns None if the repo is missing or the request fails.
    """
    token = token or os.environ.get("GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{owner}/{name}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 404:
            logger.warning("Repository not found: %s/%s", owner, name)
            return None
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.warning("Failed to fetch repo %s/%s: %s", owner, name, e)
        return None
    if not isinstance(data, dict):
        return None
    owner_login = (data.get("owner") or {}).get("login")
    repo_name = data.get("name")
    if not owner_login or not repo_name:
        return None
    return RepoInfo(
        owner=str(owner_login),
        name=str(repo_name),
        full_name=str(data.get("full_name") or f"{owner_login}/{repo_name}"),
        clone_url=str(data.get("clone_url") or f"https://github.com/{owner_login}/{repo_name}.git"),
        stars=int(data.get("stargazers_count") or 0),
        language=data.get("language"),
        description=data.get("description"),
        default_branch=str(data.get("default_branch") or "main"),
        created_at=_parse_created_at(data.get("created_at")),
    )


def fetch_trendy_repos(
    token: str | None = None,
    limit: int = 5,
    min_stars: int = 50,
    max_age_days: int | None = 30,
    language: str | Sequence[str] | None = None,
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
