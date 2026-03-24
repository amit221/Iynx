#!/usr/bin/env python3
"""
Write PR review feedback to markdown (gh CLI only).

Usage:
  python pr_review.py https://github.com/owner/repo/pull/42
  python pr_review.py owner/repo#42
  python pr_review.py --repo owner/repo --pr 42
  python pr_review.py 42 --repo owner/repo
"""

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
    from pr_review_followup import main

    raise SystemExit(main())
