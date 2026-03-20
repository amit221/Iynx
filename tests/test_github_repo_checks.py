"""Tests for GitHub repo checks (mocked HTTP)."""

from unittest.mock import MagicMock, patch

import requests

import github_repo_checks as grc


@patch("github_repo_checks.requests.get")
def test_repo_has_contributing_guide_first_path_200(mock_get: MagicMock) -> None:
    ok = MagicMock()
    ok.status_code = 200
    mock_get.return_value = ok
    assert grc.repo_has_contributing_guide("o", "r", "tok") is True
    mock_get.assert_called_once()
    assert "CONTRIBUTING.md" in mock_get.call_args[0][0]


@patch("github_repo_checks.requests.get")
def test_repo_has_contributing_guide_tries_fallback(mock_get: MagicMock) -> None:
    n404 = MagicMock()
    n404.status_code = 404
    ok = MagicMock()
    ok.status_code = 200
    mock_get.side_effect = [n404, n404, ok]
    assert grc.repo_has_contributing_guide("o", "r", "tok") is True
    assert mock_get.call_count == 3


@patch("github_repo_checks.requests.get")
def test_get_token_login(mock_get: MagicMock) -> None:
    mock_get.return_value.json.return_value = {"login": "alice"}
    mock_get.return_value.raise_for_status = MagicMock()
    assert grc.get_token_login("tok") == "alice"


@patch("github_repo_checks.requests.get")
def test_user_has_pr_to_repo_true(mock_get: MagicMock) -> None:
    mock_get.return_value.json.return_value = {"total_count": 2}
    mock_get.return_value.raise_for_status = MagicMock()
    assert grc.user_has_pr_to_repo("alice", "o", "r", "tok") is True


@patch("github_repo_checks.requests.get")
def test_user_has_pr_to_repo_false(mock_get: MagicMock) -> None:
    mock_get.return_value.json.return_value = {"total_count": 0}
    mock_get.return_value.raise_for_status = MagicMock()
    assert grc.user_has_pr_to_repo("alice", "o", "r", "tok") is False


@patch("github_repo_checks.requests.get")
def test_find_first_suitable_open_issue_returns_first_non_pr(mock_get: MagicMock) -> None:
    mock_get.return_value.json.return_value = [
        {"number": 1, "pull_request": {}},
        {"number": 7, "title": "bug"},
    ]
    mock_get.return_value.raise_for_status = MagicMock()
    assert grc.find_first_suitable_open_issue("o", "r", "tok") == 7
    mock_get.assert_called_once()
    assert mock_get.call_args[1]["params"]["labels"] == "good first issue"


@patch("github_repo_checks.requests.get")
def test_find_first_suitable_open_issue_falls_back_to_help_wanted(mock_get: MagicMock) -> None:
    empty = MagicMock()
    empty.json.return_value = []
    empty.raise_for_status = MagicMock()
    ok = MagicMock()
    ok.json.return_value = [{"number": 3, "title": "help"}]
    ok.raise_for_status = MagicMock()
    mock_get.side_effect = [empty, ok]
    assert grc.find_first_suitable_open_issue("o", "r", "tok") == 3
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[1][1]["params"]["labels"] == "help wanted"


@patch("github_repo_checks.requests.get")
def test_find_first_suitable_open_issue_none_when_all_fail(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.RequestException("nope")
    assert grc.find_first_suitable_open_issue("o", "r", "tok") is None
    assert mock_get.call_count == len(grc.SUITABLE_ISSUE_LABELS)
