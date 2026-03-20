#!/usr/bin/env python3
"""
Entrypoint for the-fixer agent.
Usage: python run.py
"""
import os
import sys

# Load .env if present
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"")
                os.environ.setdefault(k, v)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from orchestrator import main

if __name__ == "__main__":
    main()
