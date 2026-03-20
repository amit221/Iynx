"""Tests for PR helpers (subprocess mocked)."""

from unittest.mock import MagicMock, patch

import pr


def _completed(rc: int, stdout: str = "", stderr: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = rc
    m.stdout = stdout
    m.stderr = stderr
    return m


@patch("pr.subprocess.run")
def test_run_gh_invokes_gh(mock_run: MagicMock) -> None:
    mock_run.return_value = _completed(0, "ok")
    r = pr.run_gh(["api", "user"], cwd="/tmp/x", env={"A": "1"})
    assert r.returncode == 0
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0][:2] == ["gh", "api"]
    assert kwargs["cwd"] == "/tmp/x"
    assert kwargs["env"]["A"] == "1"


@patch("pr.subprocess.run")
def test_fork_and_create_pr_missing_repo(mock_run: MagicMock) -> None:
    ok, msg = pr.fork_and_create_pr("/nonexistent", "b", "t", "body", "o", "r")
    assert ok is False
    assert "does not exist" in msg
    mock_run.assert_not_called()


@patch("pr.subprocess.run")
def test_fork_and_create_pr_setup_git_fails(mock_run: MagicMock, tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    mock_run.side_effect = [
        _completed(0),  # git checkout -b
        _completed(1, stderr="nope"),  # gh auth setup-git
    ]
    ok, msg = pr.fork_and_create_pr(str(repo), "fix-x", "t", "body", "o", "r")
    assert ok is False
    assert "setup-git" in msg


@patch("pr.subprocess.run")
def test_fork_and_create_pr_fork_hard_fail(mock_run: MagicMock, tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    mock_run.side_effect = [
        _completed(0),
        _completed(0),  # setup-git
        _completed(1, stderr="fatal: not a fork"),  # gh repo fork
    ]
    ok, msg = pr.fork_and_create_pr(str(repo), "fix-x", "t", "body", "o", "r")
    assert ok is False
    assert "fork failed" in msg


@patch("pr.subprocess.run")
def test_fork_and_create_pr_fork_already_exists(mock_run: MagicMock, tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    mock_run.side_effect = [
        _completed(0),
        _completed(0),
        _completed(1, stderr="already exists"),
        _completed(0),  # push
        _completed(0, stdout="https://github.com/x/y/pull/1"),  # pr create
    ]
    ok, msg = pr.fork_and_create_pr(str(repo), "fix-x", "t", "body", "o", "r")
    assert ok is True
    assert "pull" in msg or "PR" in msg or "github" in msg


@patch("pr.subprocess.run")
def test_fork_and_create_pr_push_fails(mock_run: MagicMock, tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    mock_run.side_effect = [
        _completed(0),
        _completed(0),
        _completed(1, stderr="already a fork"),
        _completed(1, stderr="rejected"),
    ]
    ok, msg = pr.fork_and_create_pr(str(repo), "fix-x", "t", "body", "o", "r")
    assert ok is False
    assert "push" in msg


@patch("pr.subprocess.run")
def test_fork_and_create_pr_create_fails(mock_run: MagicMock, tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    mock_run.side_effect = [
        _completed(0),
        _completed(0),
        _completed(1, stderr="already exists"),
        _completed(0),
        _completed(1, stderr="pr failed"),
    ]
    ok, msg = pr.fork_and_create_pr(str(repo), "fix-x", "t", "body", "o", "r")
    assert ok is False
    assert "pr create" in msg


def test_create_pr_script_contains_commands() -> None:
    s = pr.create_pr_script("/w", "br", "my title", "my\nbody", "own", "nm")
    assert "/w" in s
    assert "br" in s
    assert "own" in s and "nm" in s
    assert "gh pr create" in s
