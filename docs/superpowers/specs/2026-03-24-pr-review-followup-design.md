# PR review follow-up (address maintainer comments)

## Summary

Define a **repeatable workflow** for iterating on an **open pull request** after a contributor or maintainer leaves **review comments** (including when the initial fix was incomplete or wrong). The same procedure applies whether the operator starts from an **existing local clone** (e.g. under `workspace/owner-repo/`) or from **only a PR URL** — always **normalize** to a git working tree on the PR’s **head branch**, capture review feedback into a **single markdown file** for agent context, then **implement → test → commit → push**.

**First deliverable (recommended):** extend the **issue-fix workflow** documentation plus a **thin helper** in this repo that fetches PR review data into a file and prints safe git hints. **Full Iynx orchestrator integration** (new Docker phase, progress JSONL) is **out of scope for v1** unless explicitly added in a later spec.

---

## Goals

1. **Single mental model** for “address PR feedback” regardless of starting point (local clone vs PR-only).
2. **Reliable branch discipline:** edits happen only on the correct **PR head** ref after an explicit normalization step; failures must be **loud** before any code changes.
3. **Review visibility:** consolidate **review comments** (and inline/thread context when available via `gh`) into one markdown file the agent reads before editing.
4. **Quality bar:** run the **target repo’s** tests (and lint/format when documented) before pushing; push updates to the **same branch** the PR already uses so CI re-runs.

## Non-goals

- Re-running Iynx **discovery** or **issue selection** for this flow.
- Auto-posting GitHub replies or resolving review threads (manual or optional `gh` is fine).
- Replacing human judgment on “request changes” vs nitpicks; the agent should ask or comment when unclear.
- New **JSONL progress phases** in v1 (optional future work: `phase: pr_review_followup`).

---

## Actors and inputs

| Input | Required | Notes |
|-------|----------|--------|
| PR URL or `owner/repo` + number | Yes | Must resolve to exactly one PR. |
| Local path to clone | Optional | If omitted or invalid, normalization uses **clone/fetch** flow. |
| `gh` CLI + auth | Yes | Same as rest of project; token must allow reading PR and reviews. |

**Convention:** All git operations target the **contribution repository** (upstream project), not the Iynx (`the-fixer`) repo unless explicitly stated.

---

## Phase 1 — Normalize working tree

**Objective:** A clean checkout on the **head ref** of the PR (contributor’s branch), with remotes suitable for **push** to the fork.

### Path A — Existing local directory

1. Verify directory is a git repo (`git rev-parse --git-dir`).
2. If this clone was created by Iynx, prefer the path under `workspace/<owner>-<repo>/` (document as convention, not a hard requirement).
3. `git fetch --all --prune` (or minimum: fetch `origin` and upstream if configured).
4. Check out the PR head. **Preferred:** `gh pr checkout <n>` from within the repo (resolves fork/upstream correctly when `gh` is authenticated).
5. **Optional but recommended before large edits:** merge or rebase **upstream** default branch into the PR branch if maintainers expect CI against latest base (document as a branch-policy choice; do not silently rebase if it would rewrite public history without operator intent).

**Failure modes:** not a git repo, detached HEAD without matching PR branch, `gh pr checkout` fails → **stop**; no file edits.

### Path B — PR only (no usable local clone)

1. Resolve `owner/repo` and PR number from URL or args.
2. **Default clone strategy (v1):** query PR metadata with `gh` (e.g. `gh pr view --json headRepository,baseRepository`).
   - If **head repository** is the **same** as upstream (`baseRepository`): clone **upstream** once; `gh pr checkout <n>` checks out the PR head ref (maintainer PR from same repo).
   - Else (**fork branch**): **fork-first** — clone using **`headRepository`’s clone URL** from `gh pr view --json` (do not assume it equals the authenticated user’s fork name). Add `upstream` pointing at the **base** repo’s clone URL. Operator must have **push** access to **head** (typically their fork).
3. `gh pr checkout <n>` in the new clone (or equivalent fetch of `pull/<n>/head` if documented fallback).

**Failure modes:** cannot resolve head repo URL, no push remote, auth failure → **stop**.

---

## Phase 2 — Capture review feedback

**Objective:** One markdown file listing actionable feedback for the agent.

### v1 artifact path and commit policy (fixed)

| Item | Rule |
|------|------|
| **Default path** | `<contribution-repo-root>/.iynx/pr-review-feedback.md` |
| **Commit policy** | **Never commit** this file. It is local agent scratch only. |
| **If `.iynx/` is not ignored** | Helper **must** support `--output PATH` (or env `IYNX_PR_REVIEW_FEEDBACK_PATH`) to write outside the repo or to a user-chosen ignored path; if default path would be **tracked** (`git check-ignore -q` fails), helper exits **`1`** with stderr explaining `--output` unless `--output` is provided. |
| **Skill doc** | States the same default path and “do not commit” rule so operators are not expected to infer from each upstream repo’s `.gitignore`. |

Rationale: aligns with other agent-facing artifacts under `.iynx/` while avoiding accidental leakage of review dumps in PR commits.

**Content should include where available:**

- PR title, number, URL, base/head refs.
- General review comments (conversation tab).
- Inline review comments with file path and line (or position) references.
- Timestamps or author logins optional (helps prioritize).

**Source (v1):** the helper **must** gather data only via **`gh` subprocess** (`gh pr view`, `gh api …`). No direct REST client in v1 (keeps auth, docs, and tests aligned with “install `gh` and login”).

**Empty review set:** if the PR has **no** review comments and **no** review bodies to include, still write the markdown file with a clear stub section, e.g. `## No review comments found`, plus PR metadata and a note to check the PR conversation for informal feedback. Exit code **`0`**. (Distinguish from **errors:** missing `gh`, auth failure, PR not found → **`2`** per table below.)

### Security

- Use **`gh`** authentication only; **do not** write `GITHUB_TOKEN`, `GH_TOKEN`, or raw Authorization headers into the feedback file or stdout.
- Treat review bodies as **untrusted text**; no shell `eval` of fetched content.

---

## Phase 3 — Implement, verify, push

1. Agent reads `.iynx/pr-review-feedback.md` (or agreed path) and addresses each thread; preserves repo conventions from `CONTRIBUTING.md` / `.iynx/context.json` if present.
2. Run **test command** (and lint/format per repo): prefer `.iynx/context.json` `test_command` / `lint_command` when present.
3. Commit with a message that reflects review follow-up (e.g. `Address review: …`).
4. `git push` to **origin** (fork) on the **same branch** as the PR head.

---

## Thin helper (v1 recommendation)

**Location:** new module under `src/` (e.g. `pr_review_followup.py`) plus a documented entry in README; exact name is an implementation detail.

**Behavior (minimum):**

| Argument / env | Behavior |
|----------------|----------|
| PR URL or `--repo owner/repo --pr N` | Resolve PR; fail fast if ambiguous. |
| `--repo-root PATH` | If set, validate path exists and is a git repo (`git rev-parse`); if not → exit **`1`**, stderr explains. If valid, use it as `<contribution-repo-root>` for default output path. If unset, cwd is used when it is a git repo; otherwise print clone/checkout instructions (exit **`0`** or **`1`** depending on whether PR resolution alone succeeded — document: “instructions only” mode). |
| `--output PATH` | Override output file path (see Phase 2 commit policy). |
| Output | Write **review markdown** to default or `--output` path. |
| Stdout | Short summary: branch name, remotes to push, suggested next commands. |
| Stderr | All errors and policy violations (e.g. tracked default path without `--output`). |

**Exit codes:** `0` — file written (including stub when no comments); `1` — usage, local path not a git repo, or default output path would be tracked without `--output`; `2` — `gh` missing, auth failure, PR not found, or GitHub API error from `gh`.

**Tests:** Optional pytest with mocked `gh` / subprocess for v1; manual smoke on Windows (PowerShell) and Unix documented in README.

---

## Documentation updates

- **`skills/issue-fix-workflow.md`:** New section **“6. PR review follow-up”** (or renumber) with the three phases above, PowerShell and bash snippets for `gh pr checkout` and fetching reviews, and pointer to the helper CLI once implemented.

---

## Future extensions (not v1)

- Orchestrator flag or env e.g. `IYNX_ADDRESS_PR=<url>` running a Docker phase analogous to `phase3_implement`.
- Append JSONL events: `phase: pr_review_fetch`, `phase: pr_review_implement` for supervising agents.

---

## Acceptance criteria (v1)

1. A reader can follow **only** the skill doc to address comments from **either** starting condition (existing clone or PR-only), without guessing branch names.
2. **Skill + helper alignment:** the skill section **“PR review follow-up”** documents the same **default output path**, **commit policy**, and **Path B clone rule** (head vs base repo) as this spec.
3. **Skill parity:** the skill includes **equivalent bash and PowerShell** snippets for Phase 1 normalization (`gh pr checkout`) and for invoking the helper (once implemented).
4. Helper (when shipped) writes a **non-empty** markdown file on success: either populated review content **or** the **“No review comments found”** stub (exit **`0`**). Exits **`2`** with **stderr** when `gh` is missing, the PR is not found, or GitHub/`gh` fails; exits **`1`** for usage/local validation errors (including tracked default path without `--output`).
5. Default artifact location and commit policy are **fully specified** above; operators are not expected to infer them from upstream `.gitignore` alone.
6. No requirement to modify **Iynx** orchestrator (`run.py` / Docker phases) for the workflow to be usable in v1.
