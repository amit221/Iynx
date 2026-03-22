"""Tests for reddit_gap lexicon scoring and pipeline (network mocked)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from reddit_gap.aggregate import compute_gap_score, finalize_rollup, merge_count_maps
from reddit_gap.classify import classify_text, merge_post_signals
from reddit_gap.lexicon import LEXICON_VERSION, compile_lexicon
from reddit_gap.pipeline import analyze_subreddit, load_seed_subs
from reddit_gap.report import write_csv, write_html, write_json


def test_compile_lexicon_dedupes() -> None:
    lex = compile_lexicon()
    assert len(lex.pain) == len({p.pattern for p in lex.pain})


def test_classify_pain_and_ai() -> None:
    lex = compile_lexicon()
    t = "ELI5 this contract in plain English — need a TL;DR"
    s = classify_text(t, lex)
    assert s.pain is True
    assert s.ai is False

    t2 = "I used ChatGPT to write this prompt for Claude 3"
    s2 = classify_text(t2, lex)
    assert s2.ai is True


def test_merge_post_signals_combines_title_body() -> None:
    lex = compile_lexicon()
    s = merge_post_signals("Ignore", "summarize this wall of text please", lex)
    assert s.pain is True


def test_compute_gap_score() -> None:
    p, a, g = compute_gap_score(pain_posts=50, ai_posts=10, n_posts=100, k=1.0)
    assert p == 500.0
    assert a == 100.0
    assert g == 400.0


def test_finalize_rollup_low_sample_flag() -> None:
    r = finalize_rollup(
        "foo",
        n_posts=5,
        pain_posts=2,
        ai_posts=1,
        both_posts=0,
        pain_hit_totals={"x": 2},
        ai_hit_totals={"y": 1},
        sidebar_flags=[],
        sidebar_reasons=[],
        subscribers=None,
    )
    assert "low_sample" in r.flags
    d = r.to_json_dict()
    assert d["evidence"]["top_pain_patterns"]


def test_merge_count_maps() -> None:
    m = merge_count_maps([{"a": 1}, {"a": 2, "b": 1}])
    assert m == {"a": 3, "b": 1}


def test_load_seed_subs(tmp_path: Path) -> None:
    p = tmp_path / "seed.txt"
    p.write_text("# c\n\n  foo  \n\nbar\n", encoding="utf-8")
    assert load_seed_subs(str(p)) == ["foo", "bar"]


def test_write_exports(tmp_path: Path) -> None:
    r = finalize_rollup(
        "demo",
        n_posts=100,
        pain_posts=30,
        ai_posts=10,
        both_posts=5,
        pain_hit_totals={},
        ai_hit_totals={},
        sidebar_flags=[],
        sidebar_reasons=[],
        subscribers=123,
    )
    write_json(tmp_path / "gap.json", [r])
    write_csv(tmp_path / "directory.csv", [r])
    write_html(tmp_path / "index.html", [r])
    data = json.loads((tmp_path / "gap.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["lexicon_version"] == LEXICON_VERSION
    assert data["subs"][0]["subreddit"] == "demo"
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "r/demo" in html


def _listing_payload(posts: list[dict]) -> dict:
    children = []
    for p in posts:
        children.append({"kind": "t3", "data": p})
    return {"data": {"children": children, "after": None}}


def test_analyze_subreddit_mocked() -> None:
    about = {
        "data": {
            "subscribers": 999,
            "public_description": "No medical advice. Not a lawyer.",
        }
    }
    posts = _listing_payload(
        [
            {"title": "ELI5 my lease", "selftext": ""},
            {"title": "Random", "selftext": "ChatGPT said this"},
        ]
    )
    with (
        patch("reddit_gap.pipeline.fetch_subreddit_about", return_value=about),
        patch("reddit_gap.pipeline.fetch_subreddit_new", return_value=posts),
        patch.dict(os.environ, {"REDDIT_GAP_SLEEP_SEC": "0"}),
    ):
        r = analyze_subreddit("testsub", max_posts=10, gap_k=1.0)

    assert r.error is None
    assert r.n_posts == 2
    assert r.pain_posts >= 1
    assert r.ai_posts >= 1
    assert r.subscribers == 999
    assert "liability_heavy" in r.sidebar_flags


def test_analyze_subreddit_fetch_error() -> None:
    with (
        patch("reddit_gap.pipeline.fetch_subreddit_about", return_value={"data": {}}),
        patch("reddit_gap.pipeline.fetch_subreddit_new", side_effect=OSError("boom")),
        patch.dict(os.environ, {"REDDIT_GAP_SLEEP_SEC": "0"}),
    ):
        r = analyze_subreddit("bad", max_posts=10)
    assert r.error == "boom"
    assert "fetch_error" in r.flags


def test_classify_sidebar_flags() -> None:
    from reddit_gap.classify import classify_sidebar

    lex = compile_lexicon()
    flags, reasons = classify_sidebar("Please: no AI content. ChatGPT banned.", lex)
    assert "no_ai_policy" in flags
    assert reasons


def test_get_user_agent_default(monkeypatch: pytest.MonkeyPatch) -> None:
    import reddit_gap.reddit_client as rc

    monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)
    ua = rc.get_user_agent()
    assert "reddit-gap" in ua.lower()


def test_fetch_json_success() -> None:
    from unittest.mock import MagicMock

    import requests

    from reddit_gap.reddit_client import fetch_json

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"x": 1}}
    mock_resp.raise_for_status = MagicMock()
    with patch.object(requests.Session, "get", return_value=mock_resp):
        assert fetch_json("https://example.com/test", session=requests.Session()) == {
            "data": {"x": 1}
        }


def test_cli_main_writes_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from reddit_gap.cli import main

    seed = tmp_path / "seed.txt"
    seed.write_text("demo\n", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setenv("REDDIT_GAP_SLEEP_SEC", "0")

    def _fake_analyze(**kwargs: object) -> object:
        return finalize_rollup(
            "demo",
            n_posts=10,
            pain_posts=2,
            ai_posts=1,
            both_posts=0,
            pain_hit_totals={},
            ai_hit_totals={},
            sidebar_flags=[],
            sidebar_reasons=[],
            subscribers=None,
        )

    monkeypatch.setattr("reddit_gap.pipeline.analyze_subreddit", _fake_analyze)
    assert main(["--seed", str(seed), "--out", str(out)]) == 0
    assert (out / "gap.json").is_file()
    assert (out / "directory.csv").is_file()
    assert (out / "index.html").is_file()


def test_cli_missing_seed() -> None:
    from reddit_gap.cli import main

    assert main(["--seed", "/nonexistent/nope.txt"]) == 1


def test_cli_empty_seed(tmp_path: Path) -> None:
    from reddit_gap.cli import main

    p = tmp_path / "empty.txt"
    p.write_text("# only comment\n", encoding="utf-8")
    assert main(["--seed", str(p)]) == 1
