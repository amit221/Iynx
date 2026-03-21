"""Tests for discovery (query building and RepoInfo parsing)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from discovery import _item_to_repo, build_search_query, fetch_repo_candidates


def test_build_search_query_includes_stars_and_created():
    q = build_search_query(min_stars=50, max_age_days=30)
    assert "stars:>50" in q
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    assert f"created:>{cutoff}" in q


def test_build_search_query_no_created_when_max_age_none():
    q = build_search_query(min_stars=100, max_age_days=None, language="python")
    assert "stars:>100" in q
    assert "created:>" not in q
    assert "language:python" in q


def test_build_search_query_multiple_languages_uses_or_group():
    q = build_search_query(
        min_stars=10,
        max_age_days=None,
        language=("javascript", "typescript", "python"),
    )
    assert "stars:>10" in q
    assert "(language:javascript OR language:typescript OR language:python)" in q


def test_item_to_repo_parses_created_at():
    item = {
        "owner": {"login": "a"},
        "name": "b",
        "full_name": "a/b",
        "clone_url": "https://github.com/a/b.git",
        "stargazers_count": 99,
        "language": "Rust",
        "description": "d",
        "default_branch": "main",
        "created_at": "2025-01-15T12:00:00Z",
    }
    r = _item_to_repo(item)
    assert r.owner == "a"
    assert r.name == "b"
    assert r.created_at is not None
    assert r.created_at.tzinfo is not None


@patch("discovery._search_repositories_page")
def test_fetch_repo_candidates_paginates_until_pool(mock_page: MagicMock) -> None:
    mock_page.side_effect = [
        {
            "items": [
                {
                    "owner": {"login": "o"},
                    "name": f"r{i}",
                    "full_name": f"o/r{i}",
                    "clone_url": f"https://github.com/o/r{i}.git",
                    "stargazers_count": 100 - i,
                    "language": None,
                    "description": None,
                    "default_branch": "main",
                    "created_at": "2025-03-01T00:00:00Z",
                }
                for i in range(30)
            ]
        },
        {
            "items": [
                {
                    "owner": {"login": "o"},
                    "name": f"rx{j}",
                    "full_name": f"o/rx{j}",
                    "clone_url": f"https://github.com/o/rx{j}.git",
                    "stargazers_count": 1,
                    "language": None,
                    "description": None,
                    "default_branch": "main",
                    "created_at": "2025-03-01T00:00:00Z",
                }
                for j in range(10)
            ]
        },
    ]
    out = fetch_repo_candidates(
        token="t", pool_size=35, min_stars=1, max_age_days=None, max_pages=5
    )
    assert len(out) == 35
    assert mock_page.call_count == 2
