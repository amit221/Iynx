# Issue Fix Workflow

Reusable workflow for fixing open-source issues: triage, implement, test, and submit.

## Repository

When the user names a repo, treat it as the work target before picking an issue or cloning anything else.

**Accepted forms**

- `owner/repo` (e.g. `python/cpython`)
- HTTPS or SSH clone URL
- Path to an existing local clone

**What to do**

1. Resolve to a local directory: use the given path if it exists and is a git repo; otherwise clone into a sensible location (e.g. workspace subfolder or the user’s stated directory).
2. `cd` there for all subsequent commands (search, edit, test, commit).
3. If the user also gives an issue or PR link, confirm it belongs to the same `owner/repo` (or explain the mismatch).

If no repo is given, assume the current workspace root or ask once for `owner/repo` / URL / path.

## Run status (supervising agents)

Long Iynx runs (`python run.py`) stream work through Docker and Cursor. A supervising agent or host process should **not** assume instant completion.

**Cadence:** Use a **scheduler (or timer) that checks run status every 60 seconds** until the run finishes or the user stops it. Sixty seconds is the default interval unless the user specifies another.

**What to check**

- **Progress file:** `.iynx-run-progress.jsonl` at the Iynx project root (or the path in `IYNX_PROGRESS_JSONL` if set). Each line is one JSON event: `phase`, `status`, `repo`, `issue`, `detail`, `exit_code`.
- **Done:** The run is finished when you see `phase` `run_complete` (read `detail` for `pr_created` vs `no_pr`, and `exit_code`).
- **Between polls:** You can still read the latest line or tail new lines since the last check; avoid tight loops.

**Implementation note:** The host may later ship a built-in scheduler that performs this 60s poll; until then, follow the same cadence when implementing supervision yourself.

## Quick Checklist

- [ ] Pick a suitable issue
- [ ] Reproduce and locate root cause
- [ ] Implement fix (preserve public APIs)
- [ ] Add regression tests
- [ ] Run format, lint, tests (per repo conventions)
- [ ] Prepare PR with conventional title and issue linkage

## 1. Issue Selection

When the orchestrator asks you to choose (issue-selection phase), pick **one** open, non-PR issue you can complete in a single focused change, or decline with `issue: null` if none fit.

Prefer issues that are:

- Scoped to one package or module
- Reproducible with unit tests or clear steps

## 2. Root Cause and Implementation

- Search the codebase for the relevant code paths
- Minimize changes; avoid touching public APIs unless required
- Use keyword-only args for new parameters: `*, new_param: str = "default"`
- Follow existing patterns in the file you modify

## 3. Testing

- Add tests mirroring the repo structure (e.g. `tests/unit_tests/`, `tests/`, `__tests__/`)
- Avoid mocks when possible; test real behavior
- Check the repo's test config (e.g. `pyproject.toml`, `jest.config.js`) for conventions

## 4. Quality Gates

Before submitting, run the repo's standard checks. Common patterns:

**Python (ruff, pytest):**
```bash
uv run ruff format .
uv run ruff check . --fix
uv run pytest tests/ -v
```

**Node/JS:**
```bash
npm run lint
npm test
```

**Make-based:**
```bash
make format
make lint
make test
```

Check `CONTRIBUTING.md`, `README.md`, or CI config for the actual commands.

## 5. PR Requirements

- **Title**: Follow the repo's convention (often `type(scope): description`, e.g. `fix(cli): resolve bug`)
- **Body**: Include `Fixes #ISSUE_NUMBER` to auto-close the issue
- **Disclaimer**: Mention AI involvement if the repo asks for it
- **Scope**: Use scopes the repo's PR lint allows (check `.github/workflows/` or contributing docs)

## 6. PR review follow-up (address maintainer comments)

Use this when an open PR already exists and reviewers left feedback. **Contribution repo** = the upstream project you fixed (not the Iynx `the-fixer` repo unless that is your target).

### Default artifact (do not commit)

- **Path:** `<contribution-repo-root>/.iynx/pr-review-feedback.md`
- **Policy:** Never commit this file. It is local scratch for the agent.
- **Gitignore:** The helper refuses the default path unless Git ignores it (`git check-ignore`). If the upstream repo does not ignore `.iynx/`, pass **`--output`** or set **`IYNX_PR_REVIEW_FEEDBACK_PATH`** to a path outside the repo (or add an ignore rule locally without committing it—prefer `--output`).

### Phase 1 — Normalize (existing clone)

From the contribution clone (e.g. `workspace/owner-repo/`):

```bash
git fetch --all --prune
gh pr checkout <PR_NUMBER>
```

```powershell
git fetch --all --prune
gh pr checkout <PR_NUMBER>
```

### Phase 1 — Normalize (PR only, no clone yet)

1. Inspect head vs base: `gh pr view <URL> --json headRepository,baseRepository`.
2. If **head** equals **base** (same `nameWithOwner`): clone that repo, then `gh pr checkout <N>`.
3. Else (fork PR): clone the **head** repo’s URL from JSON, add `upstream` to the **base** repo URL, then `gh pr checkout <N>` from that clone.

### Phase 2 — Fetch review text into markdown

From the **Iynx** project root (or any cwd if you use `--output` / env):

```bash
# Inside contribution clone; writes .iynx/pr-review-feedback.md if gitignored
python pr_review.py https://github.com/owner/repo/pull/42

python pr_review.py owner/repo#42
python pr_review.py --repo owner/repo --pr 42
python pr_review.py 42 --repo owner/repo
```

```powershell
cd path\to\contribution-clone
python path\to\the-fixer\pr_review.py "https://github.com/owner/repo/pull/42"

python path\to\the-fixer\pr_review.py --repo owner/repo --pr 42 --output "$env:TEMP\pr-review-feedback.md"
```

Requires **`gh`** installed and authenticated. If **`--output`** is omitted, **`IYNX_PR_REVIEW_FEEDBACK_PATH`** is used when set; otherwise the default is `.iynx/pr-review-feedback.md` under the contribution repo (requires that path to be gitignored).

### Phase 3 — Implement, verify, push

1. Read the markdown file; address each review thread; ask on the PR if something is ambiguous.
2. Run tests (and lint/format) using `.iynx/context.json` `test_command` / `lint_command` when present, else CONTRIBUTING.
3. Commit (do not add `pr-review-feedback.md`); push to the **same branch** as the PR head.

**Exit codes:** `0` = file written; `1` = usage or local validation; `2` = `gh`/GitHub error.

**Spec:** `docs/superpowers/specs/2026-03-24-pr-review-followup-design.md`

## Adapting to a Repo

Each repo has its own structure. Before starting:

1. Read `CONTRIBUTING.md` or the contributing guide linked from the README
2. Check `.github/PULL_REQUEST_TEMPLATE.md` for PR expectations
3. Inspect `.github/workflows/` for lint/test commands
4. Run a quick `make help` or `npm run` to see available scripts
