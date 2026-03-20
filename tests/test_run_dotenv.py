"""Tests for run.py env loading."""

import os

import pytest
import run as run_module


def test_load_dotenv_if_present_sets_vars(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IYNX_DOTENV_TEST_KEY", raising=False)
    (tmp_path / ".env").write_text("IYNX_DOTENV_TEST_KEY=fromfile\n", encoding="utf-8")
    run_module.load_dotenv_if_present(str(tmp_path))
    assert os.environ.get("IYNX_DOTENV_TEST_KEY") == "fromfile"


def test_load_dotenv_if_present_skips_missing(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IYNX_DOTENV_TEST_KEY", raising=False)
    run_module.load_dotenv_if_present(str(tmp_path))
    assert os.environ.get("IYNX_DOTENV_TEST_KEY") is None


def test_load_dotenv_if_present_respects_setdefault(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IYNX_DOTENV_TEST_KEY", "preset")
    (tmp_path / ".env").write_text("IYNX_DOTENV_TEST_KEY=fromfile\n", encoding="utf-8")
    run_module.load_dotenv_if_present(str(tmp_path))
    assert os.environ.get("IYNX_DOTENV_TEST_KEY") == "preset"


def test_load_dotenv_ignores_comments_and_blanks(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ONLY_REAL", raising=False)
    (tmp_path / ".env").write_text(
        "\n# comment\n\nONLY_REAL=value\n",
        encoding="utf-8",
    )
    run_module.load_dotenv_if_present(str(tmp_path))
    assert os.environ.get("ONLY_REAL") == "value"
