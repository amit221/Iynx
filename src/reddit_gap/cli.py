"""CLI: batch subreddits from seed file, emit JSON/CSV/HTML."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import requests

from reddit_gap.pipeline import analyze_subreddit, load_seed_subs
from reddit_gap.report import write_csv, write_html, write_json


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Score Reddit subreddits: AI-shaped pain vs AI discourse (lexicon MVP).",
    )
    p.add_argument(
        "--seed",
        default="data/reddit_gap_seed_subs.txt",
        help="Text file: one subreddit name per line (# comments ok).",
    )
    p.add_argument(
        "--out",
        default="reddit_gap_out",
        help="Output directory for gap.json, directory.csv, index.html.",
    )
    p.add_argument("--max-posts", type=int, default=100, help="Max new posts to fetch per sub.")
    p.add_argument("--gap-k", type=float, default=1.0, help="gap = pain_index - k * ai_index.")
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log each subreddit to stderr.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    seed_path = Path(args.seed)
    if not seed_path.is_file():
        print(f"Seed file not found: {seed_path}", file=sys.stderr)
        return 1

    subs = load_seed_subs(str(seed_path))
    if not subs:
        print("No subreddits in seed file.", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    session = requests.Session()
    rollups = []
    for sub in subs:
        if args.verbose:
            print(f"Fetching r/{sub} ...", file=sys.stderr)
        rollups.append(
            analyze_subreddit(
                sub,
                max_posts=args.max_posts,
                gap_k=args.gap_k,
                session=session,
            )
        )

    write_json(out_dir / "gap.json", rollups)
    write_csv(out_dir / "directory.csv", rollups)
    write_html(out_dir / "index.html", rollups)
    print(f"Wrote {out_dir / 'gap.json'}, directory.csv, index.html ({len(rollups)} subs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
