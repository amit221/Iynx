"""Unit tests for orchestrator helpers (no Docker)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import orchestrator
from discovery import RepoInfo


def test_read_json_file_missing(tmp_path: Path) -> None:
    assert orchestrator._read_json_file(tmp_path / "none.json") is None


def test_read_json_file_invalid(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    p.write_text("{bad", encoding="utf-8")
    assert orchestrator._read_json_file(p) is None


def test_read_json_file_not_dict(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    p.write_text("[1]", encoding="utf-8")
    assert orchestrator._read_json_file(p) is None


def test_read_json_file_os_error(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    p.write_text("{}", encoding="utf-8")
    with patch.object(Path, "read_text", side_effect=OSError("denied")):
        assert orchestrator._read_json_file(p) is None


def test_load_pr_draft_malformed_json_uses_defaults(tmp_path: Path) -> None:
    iynx = tmp_path / ".iynx"
    iynx.mkdir()
    (iynx / "pr-draft.json").write_text("{", encoding="utf-8")
    title, body = orchestrator.load_pr_draft(iynx, 5)
    assert "#5" in title
    assert "Fixes #5" in body


def test_load_pr_draft_empty_title_body_fallback(tmp_path: Path) -> None:
    iynx = tmp_path / ".iynx"
    iynx.mkdir()
    (iynx / "pr-draft.json").write_text(
        json.dumps({"title": "  ", "body": 123}),
        encoding="utf-8",
    )
    title, body = orchestrator.load_pr_draft(iynx, 9)
    assert "#9" in title
    assert "Fixes #9" in body


def test_load_skill_prompt_missing_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "SKILLS_DIR", tmp_path)
    assert orchestrator.load_skill_prompt() == ""


def test_load_skill_prompt_reads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "SKILLS_DIR", tmp_path)
    (tmp_path / "issue-fix-workflow.md").write_text("skill-body", encoding="utf-8")
    assert orchestrator.load_skill_prompt() == "skill-body"


@patch("orchestrator.subprocess.run")
def test_docker_run_command_shape(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0)
    orchestrator._docker_run(
        ["echo", "x"],
        env={"A": "1", "B": None},
        mount="host:guest",
        workdir="/w",
        entrypoint="bash",
    )
    cmd = mock_run.call_args[0][0]
    assert cmd[0:2] == ["docker", "run"]
    assert "--rm" in cmd
    assert "bash" in cmd
    assert "iynx-agent:latest" in cmd
    assert "-e" in cmd and "A=1" in cmd
    assert "B=" not in " ".join(cmd)


@patch("orchestrator._docker_run")
def test_clone_repo_success(
    mock_docker: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "WORKSPACE", tmp_path)
    mock_docker.return_value = MagicMock(returncode=0, stderr="", stdout="")
    repo = RepoInfo(
        owner="o",
        name="n",
        full_name="o/n",
        clone_url="https://github.com/o/n.git",
        stars=1,
        language=None,
        description=None,
        default_branch="main",
    )
    dest = orchestrator.clone_repo(repo)
    assert dest == tmp_path / "o-n"
    mock_docker.assert_called_once()
    assert "clone" in mock_docker.call_args[0][0]


@patch("orchestrator._docker_run")
def test_clone_repo_failure(
    mock_docker: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "WORKSPACE", tmp_path)
    mock_docker.return_value = MagicMock(returncode=1, stderr="clone failed", stdout="")
    repo = RepoInfo(
        owner="o",
        name="n",
        full_name="o/n",
        clone_url="https://github.com/o/n.git",
        stars=1,
        language=None,
        description=None,
        default_branch="main",
    )
    with pytest.raises(RuntimeError, match="git clone failed"):
        orchestrator.clone_repo(repo)


@patch("orchestrator._docker_run")
def test_maybe_verify_tests_runs_script(
    mock_docker: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "VERIFY_TESTS_AFTER_FIX", True)
    d = tmp_path / "repo"
    d.mkdir()
    iynx = d / ".iynx"
    iynx.mkdir()
    (iynx / "context.json").write_text(json.dumps({"test_command": "pytest -q"}), encoding="utf-8")
    mock_docker.return_value = MagicMock(returncode=0, stderr="", stdout="ok")
    assert orchestrator._maybe_verify_tests(d) is True
    mock_docker.assert_called_once()


@patch("orchestrator._docker_run")
def test_maybe_verify_tests_skips_when_disabled(
    mock_docker: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "VERIFY_TESTS_AFTER_FIX", False)
    assert orchestrator._maybe_verify_tests(tmp_path) is True
    mock_docker.assert_not_called()


@patch("orchestrator._docker_run")
def test_maybe_verify_tests_no_context_json(
    mock_docker: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "VERIFY_TESTS_AFTER_FIX", True)
    d = tmp_path / "repo"
    d.mkdir()
    assert orchestrator._maybe_verify_tests(d) is True
    mock_docker.assert_not_called()


@patch("orchestrator._docker_run")
def test_maybe_verify_tests_empty_test_command(
    mock_docker: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "VERIFY_TESTS_AFTER_FIX", True)
    d = tmp_path / "repo"
    d.mkdir()
    iynx = d / ".iynx"
    iynx.mkdir()
    (iynx / "context.json").write_text(json.dumps({"test_command": ""}), encoding="utf-8")
    assert orchestrator._maybe_verify_tests(d) is True
    mock_docker.assert_not_called()


@patch("orchestrator._docker_run")
def test_maybe_verify_tests_fails_return_false(
    mock_docker: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "VERIFY_TESTS_AFTER_FIX", True)
    d = tmp_path / "repo"
    d.mkdir()
    iynx = d / ".iynx"
    iynx.mkdir()
    (iynx / "context.json").write_text(json.dumps({"test_command": "pytest"}), encoding="utf-8")
    mock_docker.return_value = MagicMock(returncode=1, stderr="fail", stdout="")
    assert orchestrator._maybe_verify_tests(d) is False


def test_rmtree_retry_chmod_permission_then_ok() -> None:
    func = MagicMock()
    path = "/x"
    exc = PermissionError("denied")
    with patch("orchestrator.os.chmod"):
        orchestrator._rmtree_retry_chmod(func, path, exc)
    func.assert_called_once_with(path)


def test_rmtree_retry_chmod_non_permission_raises() -> None:
    with pytest.raises(ValueError):
        orchestrator._rmtree_retry_chmod(MagicMock(), "/p", ValueError("other"))


@patch("orchestrator.fetch_repo_candidates")
@patch("orchestrator.repo_has_contributing_guide", return_value=True)
@patch("orchestrator.user_has_pr_to_repo", return_value=False)
@patch("orchestrator.get_token_login", return_value="alice")
def test_discover_repos_for_run_returns_all_filtered(
    _gl: MagicMock,
    _pr: MagicMock,
    _contrib: MagicMock,
    mock_fetch: MagicMock,
) -> None:
    repos_data = [RepoInfo("a", f"r{i}", f"a/r{i}", "u", i, None, None, "main") for i in range(5)]
    mock_fetch.return_value = repos_data
    out = orchestrator.discover_repos_for_run(token="tok")
    assert len(out) == 5
    assert out[0].name == "r0"


@patch("orchestrator.fetch_repo_candidates")
@patch("orchestrator.repo_has_contributing_guide", return_value=False)
def test_discover_repos_skips_without_contributing(
    mock_contrib: MagicMock,
    mock_fetch: MagicMock,
) -> None:
    mock_fetch.return_value = [
        RepoInfo("a", "r0", "a/r0", "u", 1, None, None, "main"),
    ]
    assert orchestrator.discover_repos_for_run(token="t") == []


@patch("orchestrator.fetch_repo_candidates")
@patch("orchestrator.repo_has_contributing_guide", return_value=True)
@patch("orchestrator.user_has_pr_to_repo", return_value=True)
@patch("orchestrator.get_token_login", return_value="u")
def test_discover_repos_skips_already_contributed(
    _gl: MagicMock,
    _pr: MagicMock,
    _c: MagicMock,
    mock_fetch: MagicMock,
) -> None:
    mock_fetch.return_value = [
        RepoInfo("a", "r0", "a/r0", "u", 1, None, None, "main"),
    ]
    assert orchestrator.discover_repos_for_run(token="t") == []


def test_main_requires_cursor_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not mock sys.exit — a no-op mock lets main() continue into real discovery (network)."""
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        orchestrator.main()
    assert exc.value.code == 1


@patch("orchestrator._docker_run")
def test_run_cursor_phase_adds_model_and_force(
    mock_docker: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "k")
    monkeypatch.setenv("GITHUB_TOKEN", "g")
    mock_docker.return_value = MagicMock(returncode=0)
    (tmp_path / "iynx.cursor-agent").write_text("#!/bin/bash\necho\n", encoding="utf-8")
    orchestrator.run_cursor_phase(tmp_path, "do work", force=True)
    mock_docker.assert_called_once()
    inner = mock_docker.call_args[0][0]
    assert isinstance(inner, list)
    assert inner[0] == "-c"
    bash_script = inner[1]
    assert "cursor-agent" in bash_script
    assert "--force" in bash_script
    assert orchestrator.CURSOR_AGENT_MODEL in bash_script


@patch("orchestrator.discover_repos_for_run", return_value=[])
def test_main_runs_discovery_when_key_present(
    _disc: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "x")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    orchestrator.main()


@patch("orchestrator.run_one_repo", return_value=False)
@patch("orchestrator.discover_repos_for_run")
def test_main_runs_only_first_repo(
    mock_disc: MagicMock, mock_run: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "x")
    mock_disc.return_value = [
        RepoInfo("a", "r0", "a/r0", "u", 1, None, None, "main"),
        RepoInfo("a", "r1", "a/r1", "u", 1, None, None, "main"),
    ]
    orchestrator.main()
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0].name == "r0"


@patch("orchestrator.find_first_suitable_open_issue", return_value=99)
@patch("orchestrator.clone_repo", side_effect=RuntimeError("clone failed"))
def test_run_one_repo_runtime_error_no_retry(_clone: MagicMock, _issue: MagicMock) -> None:
    repo = RepoInfo(
        owner="o",
        name="n",
        full_name="o/n",
        clone_url="https://github.com/o/n.git",
        stars=1,
        language=None,
        description=None,
        default_branch="main",
    )
    assert orchestrator.run_one_repo(repo, max_retries=1) is False


@patch("orchestrator.time.sleep", return_value=None)
@patch("orchestrator.find_first_suitable_open_issue", return_value=99)
@patch("orchestrator.clone_repo", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=1))
def test_run_one_repo_timeout(_clone: MagicMock, _issue: MagicMock, _sleep: MagicMock) -> None:
    repo = RepoInfo(
        owner="o",
        name="n",
        full_name="o/n",
        clone_url="https://github.com/o/n.git",
        stars=1,
        language=None,
        description=None,
        default_branch="main",
    )
    assert orchestrator.run_one_repo(repo, max_retries=1) is False


@patch("orchestrator.find_first_suitable_open_issue", return_value=None)
@patch("orchestrator.clone_repo")
def test_run_one_repo_skips_clone_when_no_preflight_issue(
    mock_clone: MagicMock, _issue: MagicMock
) -> None:
    repo = RepoInfo(
        owner="o",
        name="n",
        full_name="o/n",
        clone_url="https://github.com/o/n.git",
        stars=1,
        language=None,
        description=None,
        default_branch="main",
    )
    assert orchestrator.run_one_repo(repo, max_retries=1) is False
    mock_clone.assert_not_called()
