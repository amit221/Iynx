"""Tests for GitHub repo checks (mocked HTTP)."""

from unittest.mock import MagicMock, patch

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
