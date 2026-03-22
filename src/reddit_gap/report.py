"""CSV, JSON, and minimal HTML directory export."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from reddit_gap.aggregate import SubredditRollup
from reddit_gap.lexicon import LEXICON_VERSION


def write_json(path: Path, rollups: list[SubredditRollup]) -> None:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "lexicon_version": LEXICON_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "subs": [r.to_json_dict() for r in rollups],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rollups: list[SubredditRollup]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "subreddit",
        "n_posts",
        "subscribers",
        "pain_posts",
        "ai_posts",
        "both_posts",
        "pain_index",
        "ai_penetration_index",
        "gap_score",
        "flags",
        "sidebar_flags",
        "error",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rollups, key=lambda x: (-x.gap_score, x.subreddit)):
            w.writerow(
                {
                    "subreddit": r.subreddit,
                    "n_posts": r.n_posts,
                    "subscribers": r.subscribers if r.subscribers is not None else "",
                    "pain_posts": r.pain_posts,
                    "ai_posts": r.ai_posts,
                    "both_posts": r.both_posts,
                    "pain_index": r.pain_index,
                    "ai_penetration_index": r.ai_penetration_index,
                    "gap_score": r.gap_score,
                    "flags": ";".join(r.flags),
                    "sidebar_flags": ";".join(r.sidebar_flags),
                    "error": r.error or "",
                }
            )


def write_html(path: Path, rollups: list[SubredditRollup]) -> None:
    rows = sorted(rollups, key=lambda x: (-x.gap_score, x.subreddit))
    path.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8"/>',
        "<title>Reddit AI gap directory (MVP)</title>",
        "<style>body{font-family:system-ui,sans-serif;margin:1.5rem;} table{border-collapse:collapse;width:100%;}",
        "th,td{border:1px solid #ccc;padding:0.4rem 0.6rem;text-align:left;} th{background:#f4f4f4;}",
        "tr:nth-child(even){background:#fafafa;} .num{text-align:right;font-variant-numeric:tabular-nums;}",
        ".warn{color:#a60;} .err{color:#c00;}</style></head><body>",
        "<h1>Reddit AI gap directory</h1>",
        "<p>Signals: pain-shaped posts vs AI-discourse posts per 1k (see repo spec). Not financial or legal advice.</p>",
        "<table><thead><tr>",
        "<th>Subreddit</th><th class='num'>n</th><th class='num'>pain/1k</th>",
        "<th class='num'>AI/1k</th><th class='num'>gap</th><th>Flags</th><th>Error</th>",
        "</tr></thead><tbody>",
    ]
    for r in rows:
        flag_cls = "err" if r.error else ("warn" if r.flags else "")
        parts.append("<tr>")
        parts.append(f"<td>r/{escape(r.subreddit)}</td>")
        parts.append(f"<td class='num'>{r.n_posts}</td>")
        parts.append(f"<td class='num'>{r.pain_index}</td>")
        parts.append(f"<td class='num'>{r.ai_penetration_index}</td>")
        parts.append(f"<td class='num'><strong>{r.gap_score}</strong></td>")
        parts.append(f"<td class='{flag_cls}'>{escape('; '.join(r.flags))}</td>")
        parts.append(f"<td>{escape(r.error or '')}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table></body></html>")
    path.write_text("\n".join(parts), encoding="utf-8")
