"""Edge cases for GitHub REST helpers."""

from unittest.mock import MagicMock, patch

import requests

import github_repo_checks as grc


@patch("github_repo_checks.requests.get")
def test_repo_has_contributing_request_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.RequestException("network")
    assert grc.repo_has_contributing_guide("o", "r", "t") is False


@patch("github_repo_checks.requests.get")
def test_repo_has_contributing_all_404(mock_get: MagicMock) -> None:
    mock_get.return_value.status_code = 404
    assert grc.repo_has_contributing_guide("o", "r", "t") is False
    assert mock_get.call_count == len(grc.CONTRIBUTING_PATHS)


def test_get_token_login_no_token() -> None:
    assert grc.get_token_login(None) is None
    assert grc.get_token_login("") is None


@patch("github_repo_checks.requests.get")
def test_get_token_login_request_fails(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.RequestException("x")
    assert grc.get_token_login("tok") is None


@patch("github_repo_checks.requests.get")
def test_get_token_login_bad_json(mock_get: MagicMock) -> None:
    mock_get.return_value.raise_for_status = MagicMock()
    mock_get.return_value.json.side_effect = ValueError("bad")
    assert grc.get_token_login("tok") is None


def test_user_has_pr_no_token() -> None:
    assert grc.user_has_pr_to_repo("alice", "o", "r", None) is False


@patch("github_repo_checks.requests.get")
def test_user_has_pr_search_fails(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.RequestException("x")
    assert grc.user_has_pr_to_repo("alice", "o", "r", "tok") is False


def test_api_headers_without_token() -> None:
    h = grc._api_headers(None)
    assert "Authorization" not in h
