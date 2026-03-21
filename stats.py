#!/usr/bin/env python3
"""
PR statistics CLI (GitHub label + branch pattern).

Usage:
  python stats.py [--format json|table|card|share] [--label NAME] ...
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
    from pr_stats import main

    main()
