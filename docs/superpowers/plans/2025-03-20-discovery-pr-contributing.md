# Discovery, CONTRIBUTING, PR copy, and tests — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Narrow discovery to young, starred repos the user has not contributed to, require a contribution guide (learned via API + Cursor), generate AI-written PR title/body aligned with that guide, and back the pipeline with automated tests.

**Architecture:** Extend `discovery.py` (and optionally a small `github_filters.py`) to build GitHub Search queries and apply REST checks (CONTRIBUTING present, no prior PRs from the authenticated user). Keep clone/test execution in Docker; use a short post-fix Cursor phase (or structured file output) so the host can read `pr_title` / `pr_body` instead of hardcoding strings in `orchestrator.py`. Add `pytest` with mocked HTTP for discovery and filter helpers.

**Tech Stack:** Python 3.10+, `requests`, `pytest`, `pytest-mock` (or `unittest.mock`), existing Docker + Cursor CLI flow.

**Note on `/write-plan`:** That Cursor command is deprecated; use the **writing-plans** skill for future plans.

---

## File map

| File | Responsibility |
|------|----------------|
| `src/discovery.py` | `RepoInfo` fields (`created_at` etc.), search query builder, optional `fetch_repos()` refactor |
| `src/github_repo_checks.py` (new) | Contents API: CONTRIBUTING variants; optional GraphQL/REST for "user already has PRs to this repo" |
| `src/orchestrator.py` | Wire new env vars, call filters, read `.fixer/pr-draft.json` (or similar), pass to `gh pr create` |
| `.env.example` / `README.md` | Document `FIXER_MAX_REPO_AGE_DAYS`, `FIXER_MIN_STARS`, `FIXER_REQUIRE_CONTRIBUTING`, etc. |
| `requirements.txt` | Add `pytest`, dev deps |
| `tests/test_discovery.py` (new) | Query parsing, `RepoInfo` mapping from mocked API JSON |
| `tests/test_github_repo_checks.py` (new) | Mock 200/404 for CONTRIBUTING paths; mock search for author PRs |

---

### Task 1: Test harness and discovery query behavior

**Files:**
- Create: `tests/test_discovery.py`
- Modify: `requirements.txt` (add `pytest`)
- Modify: `src/discovery.py` (only as needed to make tests pass)

- [ ] **Step 1: Write failing tests** for a pure function, e.g. `build_search_query(min_stars=50, max_age_days=30, language=None) -> str`, asserting fragments: `stars:>50`, `created:>YYYY-MM-DD` (compute expected date in test with `datetime.utcnow()` / timezone-aware pattern you choose and document).

```python
from datetime import datetime, timedelta, timezone

from discovery import build_search_query

def test_build_search_query_includes_stars_and_created():
    q = build_search_query(min_stars=50, max_age_days=30)
    assert "stars:>50" in q
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    assert f"created:>{cutoff}" in q
```

- [ ] **Step 2: Run test — expect FAIL**  
  Run: `pytest tests/test_discovery.py -v`  
  Expected: import error or missing `build_search_query`.

- [ ] **Step 3: Implement** `build_search_query` in `src/discovery.py` (no network).

- [ ] **Step 4: Run test — expect PASS**  
  Run: `pytest tests/test_discovery.py -v`

- [ ] **Step 5: Commit**  
  `git add requirements.txt src/discovery.py tests/test_discovery.py && git commit -m "test: discovery search query builder"`

---

### Task 2: `fetch_trendy_repos` uses new query and exposes `created_at`

**Files:**
- Modify: `src/discovery.py` (`fetch_trendy_repos` params: `min_stars`, `max_age_days`; extend `RepoInfo` with `created_at: datetime | None`)
- Modify: `tests/test_discovery.py`

- [ ] **Step 1: Write failing test** with `responses` **or** `unittest.mock.patch("requests.get")` returning JSON `{"items": [{"full_name": "a/b", "created_at": "2025-03-01T00:00:00Z", ...}]}` — assert `RepoInfo.created_at` is parsed.

- [ ] **Step 2: Run test — FAIL**

- [ ] **Step 3: Implement** parsing `item["created_at"]` in `fetch_trendy_repos`, merge `build_search_query` into `params["q"]`.

- [ ] **Step 4: Run test — PASS**  
  `pytest tests/test_discovery.py -v`

- [ ] **Step 5: Commit**

---

### Task 3: CONTRIBUTING file check (REST, no clone)

**Files:**
- Create: `src/github_repo_checks.py`
- Create: `tests/test_github_repo_checks.py`

- [ ] **Step 1: Write failing test** for `repo_has_contributing_guide(owner, name, token) -> bool`: mock GET `/repos/{owner}/{repo}/contents/CONTRIBUTING.md` → 200; mock 404 for root then 200 for `CONTRIBUTING` or `docs/CONTRIBUTING.md` in a second test (pick a small ordered list of paths to try; YAGNI: 2–3 paths max).

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement** using `requests.get` + `Accept: application/vnd.github.object+json` or raw contents endpoint; respect rate limits (single sequential check per repo is OK for `limit <= 20`).

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

---

### Task 4: Filter repos the authenticated user has not contributed to

**Clarification:** "Didn't contribute" = the GitHub user behind `GITHUB_TOKEN` has **no merged or open pull requests** to that upstream repo (or stricter: never opened a PR — document choice in code comment).

**Files:**
- Modify: `src/github_repo_checks.py`
- Modify: `tests/test_github_repo_checks.py`

- [ ] **Step 1: Write failing test** for `user_has_pr_to_repo(login, owner, name, token) -> bool` using mocked Search API:  
  `GET https://api.github.com/search/issues?q=repo:owner/name+type:pr+author:login` → `total_count: 0` vs `1`.

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement** `user_has_pr_to_repo`; helper `get_token_login(token)` via `GET /user`.

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

---

### Task 5: Orchestrator discovery pipeline

**Files:**
- Modify: `src/orchestrator.py`
- Modify: `src/discovery.py` (optional `discover_candidates()` that loops pages until `limit` repos pass filters)
- Modify: `.env.example`, `README.md`

- [ ] **Step 1: Add env-driven config** (defaults aligned with your spec):  
  - `FIXER_MIN_STARS` default `50`  
  - `FIXER_MAX_REPO_AGE_DAYS` default `30`  
  - `FIXER_REQUIRE_CONTRIBUTING` default `1`  
  - `FIXER_SKIP_REPOS_I_CONTRIBUTED_TO` default `1`

- [ ] **Step 2: After `fetch_trendy_repos`**, if `FIXER_REQUIRE_CONTRIBUTING`, drop repos failing `repo_has_contributing_guide`. If `FIXER_SKIP_REPOS_I_CONTRIBUTED_TO`, resolve login once, drop repos where `user_has_pr_to_repo` is true.

- [ ] **Step 3: Increase `per_page` / paginate** search if filters remove many hits (e.g. fetch 2–3 pages, cap total API calls in a constant).

- [ ] **Step 4: Manual smoke** (optional): run `python -c "from discovery import fetch_trendy_repos; ..."` with token — not required for CI if mocks cover logic.

- [ ] **Step 5: Commit**

---

### Task 6: CONTRIBUTING summary feeds Phase 3 and PR phase

**Files:**
- Modify: `src/orchestrator.py`

- [ ] **Step 1: After Phase 1**, write `contrib_summary` to a tracked file inside clone, e.g. `.fixer/contributing-summary.md` (add to `.gitignore` pattern only if needed — file lives under `workspace/` clone which is already gitignored; if written inside mounted repo, Cursor may commit it — **prefer host-written file in `dest / ".fixer" / "summary.md"`** and inject path into prompts only; do not commit).

- [ ] **Step 2: Phase 3 prompt** — include explicit instruction: "Follow the contribution and PR conventions in the summary file at `.fixer/summary.md`."

- [ ] **Step 3: New Phase 4 prompt** (short, after successful commit):  
  "Read `.fixer/summary.md` and the issue + diff. Write ONLY valid JSON to `.fixer/pr-draft.json`: `{\"title\":\"...\",\"body\":\"...\"}` matching repo PR template/conventions. Body must include: what changed, how to test, `Fixes #N`."

- [ ] **Step 4: Orchestrator** reads `.fixer/pr-draft.json` with `json.loads`; fallback to current title/body if missing/invalid.

- [ ] **Step 5: PR script** uses parsed title/body (shell-quote safely; large bodies may need `gh pr create --body-file` written from host to a temp file under `dest` — prefer **body-file** to avoid quoting bugs).

- [ ] **Step 6: Commit**

---

### Task 7: Enforce "tests working"

**Files:**
- Modify: `src/orchestrator.py` (prompts only, unless you add a verify step)
- Optional: new `src/verify.py` — run Docker one-liner to execute stored test command from Phase 1 structured output

- [ ] **Step 1: Phase 1 structured output** — extend Phase 1 prompt to require JSON in `.fixer/context.json`: `{"test_command":"...", "lint_command":null}`. Document that Phase 3 must run `test_command` and abort commit if it fails.

- [ ] **Step 2 (optional hard gate):** After Phase 3, orchestrator reads `context.json` and runs `_docker_run(["-c", test_command], ...)` once; if non-zero exit, skip PR and log (redundant if agent is honest — trade-off: slower but deterministic).

- [ ] **Step 3: Commit**

---

### Task 8: Documentation and verification

- [ ] **Step 1: README** — Discovery section updated: young repos (`<30d`), `stars>50`, CONTRIBUTING required, skip repos user already PR’d, AI PR description.

- [ ] **Step 2: Run full suite**  
  Run: `pytest tests/ -v`  
  Expected: all green.

- [ ] **Step 3: Commit**

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2025-03-20-discovery-pr-contributing.md`.

**1. Subagent-Driven (recommended)** — Use @superpowers:subagent-driven-development: fresh subagent per task, review between tasks.

**2. Inline Execution** — Use @superpowers:executing-plans in this session with checkpoints.

**Which approach do you want?**

---

## References

- GitHub Search: repository qualifiers [`stars`](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories), [`created`](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories#search-by-when-a-repository-was-created)
- Contents API: [`GET /repos/{owner}/{repo}/contents/{path}`](https://docs.github.com/en/rest/repos/contents#get-repository-content)
- Search issues for PRs by author: [`GET /search/issues`](https://docs.github.com/en/rest/search/search#search-issues-and-pull-requests)
