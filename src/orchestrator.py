"""
Orchestrator: discover repos, clone in Docker, run Cursor CLI, create PRs.

SAFETY: All repo execution (clone, npm test, etc.) runs inside Docker.
The host only runs: discovery (HTTP), docker commands, and writing bootstrap/config.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

# Ensure src is on path when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bootstrap import write_bootstrap
from discovery import RepoInfo, fetch_repo_candidates
from github_repo_checks import (
    get_token_login,
    repo_has_contributing_guide,
    user_has_pr_to_repo,
)

# Project root (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = PROJECT_ROOT / "workspace"
SKILLS_DIR = PROJECT_ROOT / "skills"
DOCKER_IMAGE = "the-fixer-agent:latest"

logger = logging.getLogger(__name__)


def _env_bool(key: str, default: str) -> bool:
    return os.environ.get(key, default).strip().lower() in ("1", "true", "yes")


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        logger.warning("Invalid integer for %s=%r; using default %s", key, raw, default)
        return default


def _env_optional_int(key: str, default: str) -> int | None:
    """Empty env means None (no filter)."""
    raw = os.environ.get(key, default).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s=%r; treating as unset (no filter)", key, raw)
        return None


def _read_json_file(path: Path) -> dict | None:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None
    return None


def load_pr_draft(fixer_dir: Path, issue_num: int) -> tuple[str, str]:
    default_title = f"fix: resolve issue #{issue_num}"
    default_body = f"Fixes #{issue_num}\n\n(AI-assisted contribution)"
    data = _read_json_file(fixer_dir / "pr-draft.json")
    if not data:
        return default_title, default_body
    title = data.get("title")
    body = data.get("body")
    if not isinstance(title, str) or not title.strip():
        title = default_title
    if not isinstance(body, str) or not body.strip():
        body = default_body
    return title.strip(), body


def discover_repos_for_run(limit: int, token: str | None) -> list[RepoInfo]:
    """
    Search GitHub, then apply CONTRIBUTING and 'already contributed' filters.
    """
    pool_default = max(limit * 20, 50)
    pool_size = min(_env_int("FIXER_DISCOVERY_POOL_SIZE", pool_default), 100)
    min_stars = _env_int("FIXER_MIN_STARS", 50)
    max_age_days = _env_optional_int("FIXER_MAX_REPO_AGE_DAYS", "30")
    max_pages = _env_int("FIXER_DISCOVERY_MAX_PAGES", 5)
    per_page = min(_env_int("FIXER_DISCOVERY_PER_PAGE", 30), 100)

    candidates = fetch_repo_candidates(
        token=token,
        pool_size=pool_size,
        min_stars=min_stars,
        max_age_days=max_age_days,
        language=os.environ.get("FIXER_LANGUAGE") or None,
        max_pages=max_pages,
        per_page=per_page,
    )
    require_contrib = _env_bool("FIXER_REQUIRE_CONTRIBUTING", "1")
    skip_contributed = _env_bool("FIXER_SKIP_REPOS_I_CONTRIBUTED_TO", "1")
    login = get_token_login(token) if skip_contributed and token else None
    if skip_contributed and token and not login:
        logger.warning("Could not resolve GitHub login; skipping 'already contributed' filter")

    filtered: list[RepoInfo] = []
    for repo in candidates:
        if require_contrib:
            if not repo_has_contributing_guide(repo.owner, repo.name, token):
                logger.debug("Skip %s: no CONTRIBUTING guide", repo.full_name)
                continue
        if skip_contributed and login:
            if user_has_pr_to_repo(login, repo.owner, repo.name, token):
                logger.debug("Skip %s: user already has PRs", repo.full_name)
                continue
        filtered.append(repo)
        if len(filtered) >= limit:
            break

    return filtered


def _maybe_verify_tests(dest: Path) -> bool:
    """Optional second run of test_command from .fixer/context.json inside Docker."""
    if not _env_bool("FIXER_VERIFY_TESTS", "0"):
        return True
    ctx = _read_json_file(dest / ".fixer" / "context.json")
    if not ctx:
        logger.warning("FIXER_VERIFY_TESTS=1 but no valid .fixer/context.json; skipping verify")
        return True
    cmd = ctx.get("test_command")
    if not isinstance(cmd, str) or not cmd.strip():
        logger.warning("No test_command in context.json; skipping verify")
        return True
    fixer = dest / ".fixer"
    fixer.mkdir(parents=True, exist_ok=True)
    script = fixer / "verify-tests.sh"
    script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\ncd /home/dev/workspace\n" + cmd.strip() + "\n",
        encoding="utf-8",
    )
    try:
        script.chmod(0o755)
    except OSError:
        pass
    r = _docker_run(
        ["bash", "/home/dev/workspace/.fixer/verify-tests.sh"],
        env={
            "GH_TOKEN": os.environ.get("GITHUB_TOKEN"),
            "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN"),
            "GIT_TERMINAL_PROMPT": "0",
        },
        mount=f"{dest.absolute()}:/home/dev/workspace",
        workdir="/home/dev/workspace",
    )
    if r.returncode != 0:
        logger.error("Verify tests failed: %s", r.stderr or r.stdout)
        return False
    return True


def _rmtree_retry_chmod(func, path, exc):
    """Windows: git packfiles are often read-only; chmod then retry delete."""
    if not isinstance(exc, PermissionError):
        raise exc
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        raise exc from None


def _remove_workspace_dir(path: Path) -> None:
    """Remove a prior clone; Windows uses rmdir /s /q to avoid rare rmtree ENOTEMPTY."""
    if not path.exists():
        return
    if os.name == "nt":
        r = subprocess.run(
            ["cmd", "/c", "rmdir", "/s", "/q", str(path.resolve())],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        if r.returncode != 0 and path.exists():
            shutil.rmtree(path, onexc=_rmtree_retry_chmod)
    else:
        shutil.rmtree(path, onexc=_rmtree_retry_chmod)


def _docker_run(
    args: list[str],
    env: dict | None = None,
    mount: str | None = None,
    workdir: str | None = None,
    entrypoint: str | None = None,
) -> subprocess.CompletedProcess:
    """Run a command inside the agent Docker container."""
    cmd = ["docker", "run", "--rm"]
    if entrypoint:
        cmd.extend(["--entrypoint", entrypoint])
    if mount:
        cmd.extend(["-v", mount])
    if workdir:
        cmd.extend(["-w", workdir])
    for k, v in (env or {}).items():
        if v is not None:
            cmd.extend(["-e", f"{k}={v}"])
    cmd.append(DOCKER_IMAGE)
    cmd.extend(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )


def clone_repo(repo: RepoInfo) -> Path:
    """
    Clone repo into workspace via Docker. Host never runs git.
    """
    dest = WORKSPACE / f"{repo.owner}-{repo.name}"
    _remove_workspace_dir(dest)
    dest.mkdir(parents=True, exist_ok=True)

    # Clone inside container; mount empty dir, clone into it (never run git on host)
    result = _docker_run(
        [
            "clone",
            "--depth",
            "1",
            "--branch",
            repo.default_branch,
            repo.clone_url,
            "/home/dev/workspace",
        ],
        env={"GIT_TERMINAL_PROMPT": "0"},
        mount=f"{dest.absolute()}:/home/dev/workspace",
        workdir="/home/dev/workspace",
        entrypoint="git",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr or result.stdout}")

    return dest


def run_cursor_phase(
    repo_path: Path,
    prompt: str,
    force: bool = False,
) -> subprocess.CompletedProcess:
    """
    Run Cursor CLI in container with workspace mounted.
    Optionally run bootstrap first.
    """
    env = {
        "CURSOR_API_KEY": os.environ.get("CURSOR_API_KEY"),
        "GH_TOKEN": os.environ.get("GITHUB_TOKEN"),
        "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN"),
    }
    args = ["-p", "--output-format", "text", "--trust"]
    model = (os.environ.get("FIXER_CURSOR_MODEL") or "composer-2").strip() or "composer-2"
    args.extend(["--model", model])
    if force:
        args.append("--force")
    args.append(prompt)

    # Run bootstrap then agent (bootstrap installs deps; agent does the work)
    quoted = " ".join(shlex.quote(a) for a in args)
    bootstrap_cmd = f"bash fixer.cursor-agent 2>/dev/null; cursor-agent {quoted}"
    return _docker_run(
        ["-c", bootstrap_cmd],
        env=env,
        mount=f"{repo_path.absolute()}:/home/dev/workspace",
        workdir="/home/dev/workspace",
        entrypoint="bash",
    )


def load_skill_prompt() -> str:
    """Load issue-fix-workflow skill for injection into prompts."""
    path = SKILLS_DIR / "issue-fix-workflow.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def run_one_repo(repo: RepoInfo, max_retries: int = 2) -> bool:
    """
    Full flow for one repo: clone, bootstrap, Cursor phases, PR.
    Returns True if PR was created, False otherwise.
    Skips to next repo on failure; retries with backoff on transient errors.
    """
    skill = load_skill_prompt()
    dest = None

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                backoff = min(30, 5 * (2**attempt))
                logger.info(
                    "Retry %d/%d for %s in %ds", attempt + 1, max_retries, repo.full_name, backoff
                )
                time.sleep(backoff)
            # 1. Clone (in Docker)
            dest = clone_repo(repo)
            logger.info("Cloned %s to %s", repo.full_name, dest)

            fixer_dir = dest / ".fixer"
            fixer_dir.mkdir(parents=True, exist_ok=True)

            # 2. Write bootstrap and Cursor rules (host writes our files; no repo code execution)
            write_bootstrap(str(dest))
            rules_dir = dest / ".cursor" / "rules"
            rules_dir.mkdir(parents=True, exist_ok=True)
            (rules_dir / "issue-fix-workflow.md").write_text(skill, encoding="utf-8")

            # 3. Phase 1: CONTRIBUTING + structured context (agent writes .fixer/*)
            phase1_prompt = f"""Read CONTRIBUTING.md (or the repo's primary contribution doc). The repository has a contribution guide.

Write two files under .fixer/ (create the directory if needed):
1) .fixer/summary.md — concise markdown: how to contribute, PR conventions, branch naming, test command, lint/format commands.
2) .fixer/context.json — valid JSON only, UTF-8, with this shape:
{{"test_command":"exact shell command to run tests from repo root","lint_command":null or string}}

Use the real test command from the repo (e.g. npm test, pytest, cargo test). If unknown, use null for test_command.
Do not commit these files.

Repo: {repo.full_name}
"""
            r1 = run_cursor_phase(dest, phase1_prompt)
            if r1.returncode != 0:
                logger.warning("Phase 1 failed: %s", r1.stderr)

            # 4. Phase 2: List good first issues
            phase2_prompt = """Using gh CLI, list open issues with labels 'good first issue' or 'help wanted'.
Run: gh issue list --label "good first issue" --limit 5
Or: gh issue list --label "help wanted" --limit 5
Pick ONE issue number that looks scoped and reproducible. Reply with just the issue number (e.g. 42).
"""
            r2 = run_cursor_phase(dest, phase2_prompt)
            if r2.returncode != 0:
                logger.warning("Phase 2 failed: %s", r2.stderr)
            issue_line = (r2.stdout or "").strip()
            issue_num = None
            for word in issue_line.split():
                if word.isdigit():
                    issue_num = int(word)
                    break
            if not issue_num:
                logger.warning("No suitable issue found; skipping repo")
                return False

            # 5. Phase 3: Implement fix
            phase3_prompt = f"""{skill}

Implement a fix for issue #{issue_num} in {repo.full_name}.

Read .fixer/summary.md and follow its contribution and PR conventions.
Read .fixer/context.json and run test_command before committing; if tests fail, fix until they pass. Do not commit if tests fail.
Do not add or commit anything under .fixer/ (keep it untracked).

Steps:
1. Read the issue: gh issue view {issue_num}
2. Find root cause and implement a minimal fix
3. Run test_command from .fixer/context.json (and lint if applicable)
4. Commit with a message matching repo conventions (e.g. fix: ... #{issue_num})

Create branch fix/issue-{issue_num} before committing.
"""
            r3 = run_cursor_phase(dest, phase3_prompt, force=True)
            if r3.returncode != 0:
                logger.warning("Phase 3 failed: %s", r3.stderr)
                if attempt < max_retries - 1:
                    continue
                return False

            if not _maybe_verify_tests(dest):
                logger.warning("Post-fix test verification failed; skipping PR")
                return False

            # 6. Phase 4: PR title/body JSON
            phase4_prompt = f"""Read .fixer/summary.md, gh issue view {issue_num}, and the latest commit message/diff.
Write ONLY valid JSON to .fixer/pr-draft.json (no markdown fence) with keys "title" and "body".
The PR must follow repository PR conventions from the summary. Body should include: summary of changes, how to test, and a line "Fixes #{issue_num}".
Do not commit this file.
"""
            r4 = run_cursor_phase(dest, phase4_prompt, force=True)
            if r4.returncode != 0:
                logger.warning("Phase 4 failed: %s", r4.stderr)

            branch = f"fix/issue-{issue_num}"
            pr_title, pr_body = load_pr_draft(fixer_dir, issue_num)
            (fixer_dir / "pr-body.md").write_text(pr_body, encoding="utf-8")

            qb = shlex.quote(branch)
            pr_title_q = shlex.quote(pr_title)
            upstream_url = f"https://github.com/{repo.owner}/{repo.name}.git"
            qu = shlex.quote(upstream_url)
            pr_script = f"""cd /home/dev/workspace && \
gh auth setup-git && \
(git checkout -b {qb} 2>/dev/null || git checkout {qb}) && \
(gh repo fork --remote=false || true) && \
LOGIN=$(gh api user -q .login) && \
git remote set-url origin "https://github.com/${{LOGIN}}/{repo.name}.git" && \
(git remote set-url upstream {qu} 2>/dev/null || git remote add upstream {qu}) && \
git push -u origin {qb} && \
gh pr create --repo {shlex.quote(repo.full_name)} --title {pr_title_q} --body-file /home/dev/workspace/.fixer/pr-body.md --base {shlex.quote(repo.default_branch)} --head "${{LOGIN}}:{branch}"
"""
            r5 = _docker_run(
                ["-c", pr_script],
                entrypoint="bash",
                env={
                    "GH_TOKEN": os.environ.get("GITHUB_TOKEN"),
                    "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN"),
                    "GIT_TERMINAL_PROMPT": "0",
                },
                mount=f"{dest.absolute()}:/home/dev/workspace",
                workdir="/home/dev/workspace",
            )
            if r5.returncode != 0:
                logger.error("PR creation failed: %s", r5.stderr or r5.stdout)
                return False

            logger.info("PR created for %s issue #%s", repo.full_name, issue_num)
            return True

        except subprocess.TimeoutExpired as e:
            logger.error("Timeout processing %s: %s", repo.full_name, e)
            if attempt < max_retries - 1:
                continue
            return False
        except RuntimeError as e:
            logger.error("Runtime error for %s: %s", repo.full_name, e)
            if attempt < max_retries - 1:
                continue
            return False
        except Exception as e:
            logger.exception(
                "Unexpected error processing %s (attempt %d): %s", repo.full_name, attempt + 1, e
            )
            if attempt < max_retries - 1:
                continue
            return False

    return False


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if not os.environ.get("CURSOR_API_KEY"):
        logger.error("CURSOR_API_KEY is required")
        sys.exit(1)
    if not os.environ.get("GITHUB_TOKEN"):
        logger.warning("GITHUB_TOKEN recommended for discovery and PR creation")

    WORKSPACE.mkdir(parents=True, exist_ok=True)

    limit = _env_int("FIXER_REPO_LIMIT", 5)
    token = os.environ.get("GITHUB_TOKEN")
    repos = discover_repos_for_run(limit=limit, token=token)
    logger.info("Discovered %d repo(s) after filters", len(repos))

    success_count = 0
    for repo in repos:
        success = run_one_repo(repo)
        if success:
            success_count += 1
        if success_count >= 1 and _env_bool("FIXER_ONE_PR_PER_RUN", "1"):
            break

    logger.info("Done. %d PR(s) created.", success_count)


if __name__ == "__main__":
    main()
