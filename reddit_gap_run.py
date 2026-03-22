#!/usr/bin/env python3
"""Reddit AI gap scoring CLI (see docs/superpowers/specs/2026-03-22-reddit-ai-gap-opportunity-design.md)."""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))


def _ensure_src_on_path() -> None:
    src = os.path.join(_ROOT, "src")
    if src not in sys.path:
        sys.path.insert(0, src)


if __name__ == "__main__":
    import run as run_module

    run_module.load_dotenv_if_present(_ROOT)
    _ensure_src_on_path()
    from reddit_gap.cli import main

    raise SystemExit(main())
