"""Tests for pr_review_followup (mocked gh/git)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import pr_review_followup as prf


def test_parse_pr_ref_url() -> None:
    v, o, r, n = prf.parse_pr_ref(
        "https://github.com/foo/bar/pull/99", None, None
    )
    assert v == "https://github.com/foo/bar/pull/99"
    assert o == "foo" and r == "bar" and n == 99


def test_parse_pr_ref_nwo() -> None:
    v, o, r, n = prf.parse_pr_ref("foo/bar#7", None, None)
    assert v == "7" and o == "foo" and r == "bar" and n == 7


def test_parse_pr_ref_repo_pr_flags() -> None:
    v, o, r, n = prf.parse_pr_ref(None, "a/b", 3)
    assert v == "3" and o == "a" and r == "b" and n == 3


def test_parse_pr_ref_bare_number_with_repo() -> None:
    v, o, r, n = prf.parse_pr_ref("12", "x/y", None)
    assert v == "12" and o == "x" and r == "y" and n == 12


def test_parse_pr_ref_invalid() -> None:
    with pytest.raises(ValueError):
        prf.parse_pr_ref(None, None, None)
    with pytest.raises(ValueError):
        prf.parse_pr_ref("not-a-url", None, None)


def test_owner_repo_from_pr_json() -> None:
    o, r = prf.owner_repo_from_pr_json(
        {"baseRepository": {"nameWithOwner": "cli/cli"}}
    )
    assert o == "cli" and r == "cli"


def test_build_markdown_stub() -> None:
    pr = {
        "title": "T",
        "url": "https://github.com/o/r/pull/1",
        "number": 1,
        "headRefName": "fix",
        "baseRefName": "main",
        "body": "",
    }
    md = prf.build_markdown(pr, [], [], [])
    assert "## No review comments found" in md
    assert "https://github.com/o/r/pull/1" in md


def test_build_markdown_with_review() -> None:
    pr = {
        "title": "T",
        "url": "u",
        "number": 1,
        "headRefName": "h",
        "baseRefName": "b",
    }
    reviews = [{"body": "Please fix", "state": "CHANGES_REQUESTED", "user": {"login": "r"}}]
    md = prf.build_markdown(pr, reviews, [], [])
    assert "Please fix" in md
    assert "## No review comments found" not in md


def test_resolve_output_with_override(tmp_path: Path) -> None:
    out = tmp_path / "x" / "f.md"
    p, rr = prf.resolve_output_path(output_cli=str(out), env_path=None, repo_root=None)
    assert p == out.resolve()
    assert out.is_file() is False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x", encoding="utf-8")
    assert p.is_file()


def test_resolve_output_default_requires_gitignore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess_run = __import__("subprocess").run
    import subprocess

    def fake_run(cmd: list, **kw):  # type: ignore[no-untyped-def]
        if cmd[:3] == ["git", "rev-parse", "--git-dir"]:
            return subprocess.CompletedProcess(cmd, 0, ".git", "")
        if cmd[:3] == ["git", "check-ignore", "-q"]:
            return subprocess.CompletedProcess(cmd, 1, "", "")
        return subprocess_run(cmd, **kw)

    with patch("pr_review_followup.subprocess.run", side_effect=fake_run):
        with pytest.raises(ValueError, match="not gitignored"):
            prf.resolve_output_path(output_cli=None, env_path=None, repo_root=tmp_path)


def test_resolve_output_default_when_ignored(tmp_path: Path) -> None:
    import subprocess

    def fake_run(cmd: list, **kw):  # type: ignore[no-untyped-def]
        if cmd[:3] == ["git", "check-ignore", "-q"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "err")

    with patch("pr_review_followup.subprocess.run", side_effect=fake_run):
        p, _ = prf.resolve_output_path(
            output_cli=None, env_path=None, repo_root=tmp_path
        )
    assert p.name == "pr-review-feedback.md"
    assert ".iynx" in str(p)


def test_main_success_with_output_mock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out.md"

    pr_json = {
        "title": "Hi",
        "url": "https://github.com/o/r/pull/2",
        "number": 2,
        "headRefName": "f",
        "baseRefName": "m",
        "baseRepository": {"nameWithOwner": "o/r"},
        "body": None,
    }

    def fake_run(cmd: list, **kw):  # type: ignore[no-untyped-def]
        import subprocess

        if cmd[:2] == ["pr", "view"]:
            return subprocess.CompletedProcess(cmd, 0, json.dumps(pr_json), "")
        if cmd[0] == "api":
            ep = cmd[1]
            if "pulls/2/reviews" in ep:
                data: list = []
            elif "pulls/2/comments" in ep:
                data = []
            elif "issues/2/comments" in ep:
                data = []
            else:
                data = []
            return subprocess.CompletedProcess(cmd, 0, json.dumps(data), "")
        raise AssertionError(f"unexpected cmd: {cmd}")

    with patch("pr_review_followup.run_gh", side_effect=fake_run):
        code = prf.main(["https://github.com/o/r/pull/2", "--output", str(out)])

    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "No review comments found" in text


def test_main_gh_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out.md"

    def boom(cmd: list, **kw):  # type: ignore[no-untyped-def]
        raise FileNotFoundError("gh")

    with patch("pr_review_followup.run_gh", side_effect=boom):
        code = prf.main(["https://github.com/o/r/pull/2", "-o", str(out)])
    assert code == 2


def test_main_no_repo_no_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    def not_git(cmd: list, **kw):  # type: ignore[no-untyped-def]
        import subprocess

        if cmd[:3] == ["git", "rev-parse", "--git-dir"]:
            return subprocess.CompletedProcess(cmd, 128, "", "not a git repo")
        raise AssertionError(cmd)

    with patch("pr_review_followup.subprocess.run", side_effect=not_git):
        code = prf.main(["o/r#1"])
    assert code == 1
