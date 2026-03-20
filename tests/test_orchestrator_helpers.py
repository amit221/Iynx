"""Tests for small orchestrator helpers (no Docker)."""

from orchestrator import load_pr_draft


def test_load_pr_draft_fallback(tmp_path) -> None:
    fixer = tmp_path / ".fixer"
    fixer.mkdir()
    title, body = load_pr_draft(fixer, 42)
    assert "42" in title
    assert "Fixes #42" in body


def test_load_pr_draft_from_json(tmp_path) -> None:
    fixer = tmp_path / ".fixer"
    fixer.mkdir()
    (fixer / "pr-draft.json").write_text(
        '{"title":"docs: fix typo","body":"Summary here.\\n\\nFixes #7"}',
        encoding="utf-8",
    )
    title, body = load_pr_draft(fixer, 99)
    assert title == "docs: fix typo"
    assert "Fixes #7" in body
