"""Extra discovery tests (parsing, API retries)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from discovery import (
    _parse_created_at,
    _search_repositories_page,
    fetch_repo_candidates,
    fetch_trendy_repos,
)


def test_parse_created_at_none() -> None:
    assert _parse_created_at(None) is None
    assert _parse_created_at("") is None


def test_parse_created_at_z_suffix() -> None:
    dt = _parse_created_at("2024-06-01T00:00:00Z")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_created_at_invalid() -> None:
    assert _parse_created_at("not-a-date") is None


@patch("discovery.requests.get")
def test_search_repositories_page_success(mock_get: MagicMock) -> None:
    resp = MagicMock()
    resp.json.return_value = {"items": []}
    resp.raise_for_status = MagicMock()
    mock_get.return_value = resp
    out = _search_repositories_page("q", 1, 30, "tok")
    assert out == {"items": []}
    mock_get.assert_called_once()
    assert "Bearer tok" in mock_get.call_args[1]["headers"]["Authorization"]


@patch("discovery.time.sleep", return_value=None)
@patch("discovery.requests.get")
def test_search_repositories_page_retries(mock_get: MagicMock, _sleep: MagicMock) -> None:
    ok = MagicMock()
    ok.json.return_value = {"items": [1]}
    ok.raise_for_status = MagicMock()
    mock_get.side_effect = [
        requests.RequestException("fail"),
        requests.RequestException("fail"),
        ok,
    ]
    out = _search_repositories_page("q", 1, 30, None)
    assert out == {"items": [1]}
    assert mock_get.call_count == 3


@patch("discovery.time.sleep", return_value=None)
@patch("discovery.requests.get")
def test_search_repositories_page_raises_after_retries(
    mock_get: MagicMock, _sleep: MagicMock
) -> None:
    mock_get.side_effect = requests.RequestException("always")
    with pytest.raises(requests.RequestException):
        _search_repositories_page("q", 1, 30, None)
    assert mock_get.call_count == 3


@patch("discovery._search_repositories_page")
def test_fetch_repo_candidates_stops_on_empty_page(mock_page: MagicMock) -> None:
    mock_page.side_effect = [
        {
            "items": [
                {
                    "owner": {"login": "a"},
                    "name": "b",
                    "full_name": "a/b",
                    "clone_url": "u",
                    "stargazers_count": 1,
                    "default_branch": "main",
                }
            ]
        },
        {"items": []},
    ]
    repos = fetch_repo_candidates(
        token="t", pool_size=10, min_stars=1, max_age_days=None, max_pages=5
    )
    assert len(repos) == 1


@patch("discovery.fetch_repo_candidates")
def test_fetch_trendy_repos_delegates(mock_fetch: MagicMock) -> None:
    mock_fetch.return_value = []
    fetch_trendy_repos(token="x", limit=3, min_stars=10, max_age_days=None)
    mock_fetch.assert_called_once()
    assert mock_fetch.call_args.kwargs["pool_size"] == 3
