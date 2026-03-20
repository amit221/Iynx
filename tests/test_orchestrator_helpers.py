"""Tests for small orchestrator helpers (no Docker)."""

from orchestrator import load_pr_draft


def test_load_pr_draft_fallback(tmp_path) -> None:
    iynx = tmp_path / ".iynx"
    iynx.mkdir()
    title, body = load_pr_draft(iynx, 42)
    assert "42" in title
    assert "Fixes #42" in body


def test_load_pr_draft_from_json(tmp_path) -> None:
    iynx = tmp_path / ".iynx"
    iynx.mkdir()
    (iynx / "pr-draft.json").write_text(
        '{"title":"docs: fix typo","body":"Summary here.\\n\\nFixes #7"}',
        encoding="utf-8",
    )
    title, body = load_pr_draft(iynx, 99)
    assert title == "docs: fix typo"
    assert "Fixes #7" in body
