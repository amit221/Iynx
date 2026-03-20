"""
GitHub REST helpers: CONTRIBUTING presence and whether the token user already opened PRs.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# Tried in order via Contents API (paths relative to repo root).
CONTRIBUTING_PATHS = (
    "CONTRIBUTING.md",
    "CONTRIBUTING",
    ".github/CONTRIBUTING.md",
)


def _api_headers(token: str | None) -> dict[str, str]:
    h = {"Accept": "application/vnd.github.v3+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def repo_has_contributing_guide(owner: str, name: str, token: str | None) -> bool:
    """True if any known CONTRIBUTING file exists at the default branch."""
    headers = _api_headers(token)
    for path in CONTRIBUTING_PATHS:
        enc = quote(path, safe="")
        url = f"https://api.github.com/repos/{owner}/{name}/contents/{enc}"
        try:
            r = requests.get(url, headers=headers, timeout=20)
        except requests.RequestException as e:
            logger.warning("CONTRIBUTING check failed for %s/%s (%s): %s", owner, name, path, e)
            return False
        if r.status_code == 200:
            return True
    return False


def get_token_login(token: str | None) -> str | None:
    """Return login for the authenticated user, or None."""
    if not token:
        return None
    try:
        r = requests.get(
            "https://api.github.com/user",
            headers=_api_headers(token),
            timeout=20,
        )
        r.raise_for_status()
        login = r.json().get("login")
        return str(login) if login else None
    except (requests.RequestException, ValueError, TypeError) as e:
        logger.warning("Could not resolve GitHub login: %s", e)
        return None


def find_first_suitable_open_issue(
    owner: str,
    name: str,
    token: str | None,
    *,
    per_page: int = 100,
) -> int | None:
    """
    Return one open issue number (not a PR), newest first.

    Used for preflight (repo has something to work on). The agent may pick a
    different issue after clone via .iynx/chosen-issue.json.
    """
    headers = _api_headers(token)
    cap = min(max(per_page, 1), 100)
    url = f"https://api.github.com/repos/{owner}/{name}/issues"
    params = {
        "state": "open",
        "per_page": cap,
        "sort": "created",
        "direction": "desc",
    }
    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Issue list failed for %s/%s: %s", owner, name, e)
        return None
    items = r.json()
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("pull_request") is not None:
            continue
        num = item.get("number")
        if isinstance(num, int) and num > 0:
            return num
    return None


def validate_open_non_pr_issue(
    owner: str,
    name: str,
    issue_num: int,
    token: str | None,
) -> int | None:
    """
    Return issue_num if it is an open issue (not a pull request) on owner/name.
    """
    if issue_num < 1:
        return None
    headers = _api_headers(token)
    url = f"https://api.github.com/repos/{owner}/{name}/issues/{issue_num}"
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        item = r.json()
    except requests.RequestException as e:
        logger.warning("Issue fetch failed for %s/%s#%s: %s", owner, name, issue_num, e)
        return None
    if not isinstance(item, dict):
        return None
    if str(item.get("state") or "").lower() != "open":
        return None
    if item.get("pull_request") is not None:
        return None
    num = item.get("number")
    return int(num) if isinstance(num, int) and num > 0 else None


def user_has_pr_to_repo(login: str, owner: str, name: str, token: str | None) -> bool:
    """
    True if `login` has any pull request (open or closed) to owner/name.

    Uses the Search API (same semantics as web search for type:pr author:login).
    """
    if not token:
        return False
    q = f"repo:{owner}/{name} is:pr author:{login}"
    try:
        r = requests.get(
            "https://api.github.com/search/issues",
            headers=_api_headers(token),
            params={"q": q, "per_page": 1},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        total = int(data.get("total_count") or 0)
        return total > 0
    except (requests.RequestException, ValueError, TypeError) as e:
        logger.warning("PR search failed for %s/%s: %s", owner, name, e)
        return False
