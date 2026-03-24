"""
Fetch GitHub PR review feedback into a markdown file via `gh` only.

See docs/superpowers/specs/2026-03-24-pr-review-followup-design.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_RELATIVE_FEEDBACK = Path(".iynx") / "pr-review-feedback.md"

_PR_URL_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?(?:#.*)?$",
    re.IGNORECASE,
)
_NWO_HASH_RE = re.compile(r"^([^#\s]+/[^#\s]+)#(\d+)\s*$")


def parse_pr_ref(
    pr_ref: str | None, repo: str | None, pr_num: int | None
) -> tuple[str, str, str, int]:
    """
    Return (gh_view_arg, owner, repo_name, number).

    gh_view_arg is passed to `gh pr view` (URL or number as str).
    owner/repo_name come from URL or --repo (for non-URL `gh api` paths before pr view).
    """
    if pr_num is not None and repo:
        owner, _, name = repo.strip().partition("/")
        if not owner or not name or "/" in name:
            raise ValueError(f"invalid --repo (expected owner/name): {repo!r}")
        return str(pr_num), owner, name, pr_num

    if pr_ref and pr_ref.strip().isdigit() and repo:
        owner, _, name = repo.strip().partition("/")
        if not owner or not name or "/" in name:
            raise ValueError(f"invalid --repo (expected owner/name): {repo!r}")
        n = int(pr_ref.strip())
        return str(n), owner, name, n

    if not pr_ref or not pr_ref.strip():
        raise ValueError("pass a PR URL, owner/repo#number, or --repo and --pr")

    s = pr_ref.strip()
    m = _PR_URL_RE.match(s)
    if m:
        return s, m.group(1), m.group(2), int(m.group(3))

    m2 = _NWO_HASH_RE.match(s)
    if m2:
        nwo, num_s = m2.group(1), m2.group(2)
        owner, _, name = nwo.partition("/")
        if not owner or not name or "/" in name:
            raise ValueError(f"invalid owner/repo in {s!r}")
        return num_s, owner, name, int(num_s)

    raise ValueError(
        "PR reference must be a github.com pull URL or owner/repo#number, "
        "or use --repo owner/name --pr N"
    )


def owner_repo_from_pr_json(data: dict[str, Any]) -> tuple[str, str]:
    br = data.get("baseRepository")
    if not isinstance(br, dict):
        raise ValueError("gh pr view JSON missing baseRepository")
    nwo = br.get("nameWithOwner")
    if not isinstance(nwo, str) or "/" not in nwo:
        raise ValueError("gh pr view JSON missing baseRepository.nameWithOwner")
    owner, _, name = nwo.partition("/")
    if not owner or not name:
        raise ValueError(f"invalid nameWithOwner: {nwo!r}")
    return owner, name


def pr_number_from_json(data: dict[str, Any]) -> int:
    n = data.get("number")
    if not isinstance(n, int):
        raise ValueError("gh pr view JSON missing number")
    return n


def _gh_repo_flag(owner: str, repo: str) -> list[str]:
    return ["--repo", f"{owner}/{repo}"]


def run_gh(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        encoding="utf-8",
        errors="replace",
    )


def is_git_repo(path: Path) -> bool:
    r = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=str(path),
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def path_is_gitignored(repo_root: Path, relative_posix: str) -> bool:
    """True if `git check-ignore -q` accepts the path (ignored)."""
    r = subprocess.run(
        ["git", "check-ignore", "-q", relative_posix],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        return True
    if r.returncode == 1:
        return False
    raise RuntimeError(
        f"git check-ignore failed in {repo_root}: {r.stderr or r.stdout or r.returncode}"
    )


def current_branch(repo_root: Path) -> str | None:
    r = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    b = (r.stdout or "").strip()
    return b or None


def _fence_body(text: str) -> str:
    """Wrap user-controlled text in a markdown fence; avoid breaking on ```."""
    safe = text.replace("```", "``\\`")
    return f"```text\n{safe}\n```"


def _author_login(author: Any) -> str:
    if isinstance(author, dict):
        login = author.get("login")
        if isinstance(login, str):
            return login
    return "unknown"


def build_markdown(
    pr: dict[str, Any],
    reviews: list[dict[str, Any]],
    pull_comments: list[dict[str, Any]],
    issue_comments: list[dict[str, Any]],
) -> str:
    lines: list[str] = [
        "# PR review feedback",
        "",
        "Local agent scratch — **do not commit** (see Iynx skill: PR review follow-up).",
        "",
        "## Metadata",
        "",
    ]
    title = pr.get("title")
    lines.append(f"- **Title:** {title if isinstance(title, str) else '—'}")
    url = pr.get("url")
    lines.append(f"- **URL:** {url if isinstance(url, str) else '—'}")
    num = pr.get("number")
    lines.append(f"- **Number:** {num if isinstance(num, int) else '—'}")
    hr = pr.get("headRefName")
    br = pr.get("baseRefName")
    lines.append(f"- **Head:** `{hr}`" if isinstance(hr, str) else "- **Head:** —")
    lines.append(f"- **Base:** `{br}`" if isinstance(br, str) else "- **Base:** —")
    lines.append("")

    body = pr.get("body")
    if isinstance(body, str) and body.strip():
        lines.extend(["## PR body", "", _fence_body(body), ""])

    has_reviews = any(
        isinstance(r.get("body"), str) and (r.get("body") or "").strip() for r in reviews
    )
    has_inline = bool(pull_comments)
    has_issue = any(
        isinstance(c.get("body"), str) and (c.get("body") or "").strip() for c in issue_comments
    )

    if reviews:
        lines.append("## Reviews (submitted reviews)")
        lines.append("")
        for i, rev in enumerate(reviews, 1):
            state = rev.get("state")
            user = _author_login(rev.get("user"))
            submitted = rev.get("submitted_at") or rev.get("submittedAt") or "—"
            lines.append(f"### Review {i} ({user}, {state}, {submitted})")
            lines.append("")
            rb = rev.get("body")
            if isinstance(rb, str) and rb.strip():
                lines.append(_fence_body(rb))
            else:
                lines.append("*(no body)*")
            lines.append("")

    if pull_comments:
        lines.append("## Inline review comments (on diff)")
        lines.append("")
        for i, c in enumerate(pull_comments, 1):
            path = c.get("path") or "—"
            line = c.get("line")
            side = c.get("side") or ""
            user = _author_login(c.get("user"))
            loc = f"`{path}`" + (f" line {line}" if line is not None else "")
            lines.append(f"### Inline {i} ({user}) {loc} {side}".rstrip())
            lines.append("")
            cb = c.get("body")
            if isinstance(cb, str) and cb.strip():
                lines.append(_fence_body(cb))
            else:
                lines.append("*(no body)*")
            lines.append("")

    if issue_comments:
        lines.append("## Issue / conversation comments")
        lines.append("")
        for i, c in enumerate(issue_comments, 1):
            user = _author_login(c.get("user"))
            created = c.get("created_at") or c.get("createdAt") or "—"
            lines.append(f"### Comment {i} ({user}, {created})")
            lines.append("")
            cb = c.get("body")
            if isinstance(cb, str) and cb.strip():
                lines.append(_fence_body(cb))
            else:
                lines.append("*(no body)*")
            lines.append("")

    if not (has_reviews or has_inline or has_issue):
        lines.extend(
            [
                "## No review comments found",
                "",
                "There are no submitted review bodies, inline review comments, or issue "
                "comments with text on this PR (per GitHub API). Check the PR conversation "
                "on GitHub for informal notes or new threads.",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def fetch_pr_json(view_arg: str, owner: str, repo: str) -> dict[str, Any]:
    """Call `gh pr view`. Use a full GitHub PR URL as `view_arg` OR pass number + owner/repo."""
    fields = (
        "title,url,number,headRefName,baseRefName,baseRepository,headRepository,body,author,state"
    )
    va = view_arg.strip()
    if _PR_URL_RE.match(va):
        cmd = ["pr", "view", va, "--json", fields]
    else:
        cmd = ["pr", "view", va, *_gh_repo_flag(owner, repo), "--json", fields]
    proc = run_gh(cmd)
    if proc.returncode != 0:
        raise GhError(proc.stderr.strip() or proc.stdout.strip() or "gh pr view failed")
    return json.loads(proc.stdout)


def fetch_json_list(endpoint: str) -> list[dict[str, Any]]:
    """GET repos/... API path; paginate into one list."""
    out: list[dict[str, Any]] = []
    page = 1
    per_page = 100
    while True:
        proc = run_gh(
            [
                "api",
                f"{endpoint}?per_page={per_page}&page={page}",
            ]
        )
        if proc.returncode != 0:
            raise GhError(proc.stderr.strip() or proc.stdout.strip() or f"gh api {endpoint} failed")
        chunk = json.loads(proc.stdout)
        if not isinstance(chunk, list):
            raise GhError(f"expected list from gh api {endpoint}")
        out.extend(chunk)
        if len(chunk) < per_page:
            break
        page += 1
        if page > 100:
            break
    return out


class GhError(Exception):
    pass


def resolve_output_path(
    *,
    output_cli: str | None,
    env_path: str | None,
    repo_root: Path | None,
) -> tuple[Path, Path | None]:
    """
    Return (absolute output file path, repo_root if used for default path).

    Raises ValueError for exit-1 cases (stderr to be printed by caller).
    """
    override = output_cli or (env_path or "").strip() or None
    if override:
        p = Path(override).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p, repo_root

    if repo_root is None:
        raise ValueError(
            "Cannot use default output path without a contribution repo root. "
            "Run from inside the clone, pass --repo-root PATH, or pass --output PATH "
            "(or set IYNX_PR_REVIEW_FEEDBACK_PATH)."
        )

    rel = DEFAULT_RELATIVE_FEEDBACK.as_posix()
    try:
        if not path_is_gitignored(repo_root, rel):
            raise ValueError(
                f"Default output {rel} is not gitignored in {repo_root}. "
                "Use --output PATH or IYNX_PR_REVIEW_FEEDBACK_PATH to write elsewhere, "
                "or add an ignore rule for .iynx/ in that repo."
            )
    except RuntimeError as e:
        raise ValueError(str(e)) from e

    full = (repo_root / DEFAULT_RELATIVE_FEEDBACK).resolve()
    full.parent.mkdir(parents=True, exist_ok=True)
    return full, repo_root


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Write PR review feedback to markdown using gh CLI only."
    )
    p.add_argument(
        "pr_ref",
        nargs="?",
        default=None,
        help="PR URL or owner/repo#number",
    )
    p.add_argument("--repo", default=None, help="owner/name (with --pr)")
    p.add_argument("--pr", type=int, default=None, help="PR number (with --repo)")
    p.add_argument(
        "--repo-root",
        dest="repo_root",
        default=None,
        help="Contribution repo root (for default .iynx/pr-review-feedback.md)",
    )
    p.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (no git repo required)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        view_arg, owner, repo_name, _pr_num = parse_pr_ref(args.pr_ref, args.repo, args.pr)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    env_out = os.environ.get("IYNX_PR_REVIEW_FEEDBACK_PATH", "").strip() or None

    repo_root_path: Path | None = None
    if args.repo_root:
        rr = Path(args.repo_root).expanduser().resolve()
        if not rr.is_dir():
            print(f"--repo-root is not a directory: {rr}", file=sys.stderr)
            return 1
        if not is_git_repo(rr):
            print(f"--repo-root is not a git repository: {rr}", file=sys.stderr)
            return 1
        repo_root_path = rr
    else:
        cwd = Path.cwd().resolve()
        if is_git_repo(cwd):
            repo_root_path = cwd

    try:
        out_path, _used_root = resolve_output_path(
            output_cli=args.output,
            env_path=env_out,
            repo_root=repo_root_path,
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    try:
        pr_data = fetch_pr_json(view_arg, owner, repo_name)
        api_owner, api_repo = owner_repo_from_pr_json(pr_data)
        pr_n = pr_number_from_json(pr_data)
        if api_owner != owner or api_repo != repo_name:
            owner, repo_name = api_owner, api_repo

        base = f"repos/{owner}/{repo_name}"
        reviews = fetch_json_list(f"{base}/pulls/{pr_n}/reviews")
        pull_comments = fetch_json_list(f"{base}/pulls/{pr_n}/comments")
        issue_comments = fetch_json_list(f"{base}/issues/{pr_n}/comments")

        md = build_markdown(pr_data, reviews, pull_comments, issue_comments)
    except FileNotFoundError:
        print(
            "gh executable not found; install GitHub CLI and ensure it is on PATH.", file=sys.stderr
        )
        return 2
    except GhError as e:
        print(str(e), file=sys.stderr)
        return 2
    except (json.JSONDecodeError, OSError) as e:
        print(f"Failed to read gh output or write file: {e}", file=sys.stderr)
        return 2

    try:
        out_path.write_text(md, encoding="utf-8")
    except OSError as e:
        print(f"Failed to write {out_path}: {e}", file=sys.stderr)
        return 2

    print(f"Wrote review feedback: {out_path}")
    print(f"PR: {pr_data.get('url', '—')}")
    head_ref = pr_data.get("headRefName")
    if isinstance(head_ref, str) and head_ref:
        print(
            f"This tool does not commit or push. After you fix and commit, push the PR branch:\n"
            f"  git push origin {head_ref}"
        )
    else:
        print(
            "This tool does not commit or push. After you fix and commit, push your PR branch "
            "(same ref as the PR head on GitHub)."
        )
    if repo_root_path and out_path.is_relative_to(repo_root_path):
        br = current_branch(repo_root_path)
        if br:
            print(f"Current branch (in {repo_root_path}): {br}")
            if isinstance(head_ref, str) and head_ref and br != head_ref:
                print(
                    f"Warning: branch '{br}' differs from PR head '{head_ref}'. "
                    "Checkout the PR head before pushing or the PR will not update.",
                    file=sys.stderr,
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
