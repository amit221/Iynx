"""
PR automation: fork, push branch, create PR.
Designed to run inside the Docker container (via gh CLI).
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def run_gh(args: list[str], cwd: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run gh CLI with given args."""
    env = env or {}
    full_env = {**os.environ, **env}
    return subprocess.run(
        ["gh", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=full_env,
        timeout=120,
    )


def fork_and_create_pr(
    repo_path: str,
    branch_name: str,
    pr_title: str,
    pr_body: str,
    upstream_owner: str,
    upstream_repo: str,
) -> tuple[bool, str]:
    """
    Fork the upstream repo (if not already forked), push branch, create PR.

    Must run inside container where gh is authenticated.

    Returns:
        (success, message)
    """
    if not Path(repo_path).exists():
        return False, f"Repo path does not exist: {repo_path}"

    # Ensure we're on the right branch
    subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=repo_path,
        capture_output=True,
        timeout=10,
    )

    # Wire git HTTPS to use gh + token (same as `gh auth setup-git`)
    setup = subprocess.run(
        ["gh", "auth", "setup-git"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        env={**os.environ},
    )
    if setup.returncode != 0:
        return False, f"gh auth setup-git failed: {setup.stderr or setup.stdout}"

    # Fork (creates fork if needed; adds fork as origin, renames base to upstream)
    fork_result = run_gh(
        ["repo", "fork", "--remote=true", "--remote-name=origin"],
        cwd=repo_path,
    )
    if fork_result.returncode != 0:
        # May already be a fork or we're in a fork
        err = (fork_result.stderr or "").lower()
        if "already exists" not in err and "already a fork" not in err:
            return False, f"gh repo fork failed: {fork_result.stderr or fork_result.stdout}"

    # Push branch to fork (origin = our fork after gh repo fork)
    push_result = subprocess.run(
        ["git", "push", "-u", "origin", branch_name],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if push_result.returncode != 0:
        return False, f"git push failed: {push_result.stderr or push_result.stdout}"

    # Create PR
    pr_result = run_gh(
        [
            "pr",
            "create",
            "--title",
            pr_title,
            "--body",
            pr_body,
            "--base",
            "main",
            "--head",
            branch_name,
        ],
        cwd=repo_path,
    )
    if pr_result.returncode != 0:
        return False, f"gh pr create failed: {pr_result.stderr or pr_result.stdout}"

    return True, pr_result.stdout or "PR created"


def create_pr_script(
    repo_path: str,
    branch_name: str,
    pr_title: str,
    pr_body: str,
    upstream_owner: str,
    upstream_repo: str,
) -> str:
    """
    Generate a bash script that performs fork + push + pr create.
    Used when we need to run this from a shell (e.g. docker exec).
    """
    return f"""#!/usr/bin/env bash
set -euo pipefail
cd "{repo_path}"

gh auth setup-git

# Ensure branch exists
git checkout -b "{branch_name}" 2>/dev/null || git checkout "{branch_name}"

# Fork and set remotes
gh repo fork --remote=true --remote-name=origin 2>/dev/null || true
git remote add upstream "https://github.com/{upstream_owner}/{upstream_repo}.git" 2>/dev/null || true

# Push to fork
GIT_TERMINAL_PROMPT=0 git push -u origin "{branch_name}"

# Create PR
gh pr create --title "{pr_title}" --body "{pr_body}" --base main --head "{branch_name}"
"""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 7:
        print("Usage: pr.py <repo_path> <branch> <title> <body> <owner> <repo>")
        sys.exit(1)

    ok, msg = fork_and_create_pr(
        repo_path=sys.argv[1],
        branch_name=sys.argv[2],
        pr_title=sys.argv[3],
        pr_body=sys.argv[4],
        upstream_owner=sys.argv[5],
        upstream_repo=sys.argv[6],
    )
    if ok:
        print(msg)
    else:
        print("Error:", msg, file=sys.stderr)
        sys.exit(1)
