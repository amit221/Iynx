"""
GitHub REST helpers: CONTRIBUTING presence and whether the token user already opened PRs.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# Tried in order via Contents API (paths relative to repo root).
CONTRIBUTING_PATHS = (
    "CONTRIBUTING.md",
    "CONTRIBUTING",
    ".github/CONTRIBUTING.md",
)


def _api_headers(token: Optional[str]) -> dict[str, str]:
    h = {"Accept": "application/vnd.github.v3+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def repo_has_contributing_guide(owner: str, name: str, token: Optional[str]) -> bool:
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


def get_token_login(token: Optional[str]) -> Optional[str]:
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


def user_has_pr_to_repo(login: str, owner: str, name: str, token: Optional[str]) -> bool:
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
