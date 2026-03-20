#!/usr/bin/env python3
"""
Entrypoint for the Iynx agent.

Usage:
  python run.py
  python run.py owner/repo [issue_number]
  python run.py https://github.com/owner/repo [issue_number]

Or set IYNX_TARGET_REPO and optional IYNX_TARGET_ISSUE in the environment.
"""

import os
import sys


def load_dotenv_if_present(root_dir: str) -> None:
    """Load KEY=value pairs from root_dir/.env into os.environ (setdefault only)."""
    env_path = os.path.join(root_dir, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"")
                os.environ.setdefault(k, v)


_ROOT = os.path.dirname(os.path.abspath(__file__))


def _ensure_src_on_path() -> None:
    src = os.path.join(_ROOT, "src")
    if src not in sys.path:
        sys.path.insert(0, src)


if __name__ == "__main__":
    load_dotenv_if_present(_ROOT)
    _ensure_src_on_path()
    from orchestrator import main

    main()
