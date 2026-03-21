# GitHub PR statistics & shareable console card

## Summary

Add a **GitHub-only** statistics path that counts pull requests **you** opened that match a **label** and a **head-branch** pattern, across **all repositories**. Provide multiple output formats, including a **card** (alias **share**) view optimized for **screenshots** and social sharing. **Orchestrator** must apply the same label when creating PRs so search results stay aligned with the workflow.

Local `.iynx-run-progress.jsonl` aggregates are **out of scope** for this feature.

---

## Goals

1. **Classify** matching PRs into: **merged**, **open**, **closed without merge** (and derived **total**).
2. **Identify** PRs with **both**:
   - A configurable **label** (applied at `gh pr create` time).
   - A configurable **head ref regex** (default matches existing branch naming `fix/issue-{n}`).
3. **Scope:** GitHub-wide for the authenticated user (same universe as “all my PRs,” then filtered).
4. **UX:** Machine-readable **JSON**, plain **table**, and a **card** / **share** terminal view (aliases; same renderer) with optional ANSI color and `--no-color`.

## Non-goals

- Run counts, phase breakdowns, or any reporting from local JSONL.
- Web UI, scheduled reports, or persistence of stats.
- GitHub Actions or CI minute statistics.
- GraphQL API (REST Search + REST PR details is enough for v1; revisit if rate limits bite).

---

## Configuration

| Variable | Required | Purpose |
|----------|----------|---------|
| `GITHUB_TOKEN` | Yes for stats CLI | Same token pattern as the rest of the project (`Bearer` to GitHub API). Use a token with **`repo`** scope if you need PRs in **private** repositories; otherwise search may omit them. |
| `IYNX_PR_LABEL` | Yes for **creating** labeled PRs from orchestrator | Passed to `gh pr create --label`. Document in README and `.env.example`. |
| `IYNX_STATS_LABEL` | Optional on stats CLI | Override label used when **querying** (defaults to `IYNX_PR_LABEL` if set, else must be passed via CLI or error). |
| `IYNX_STATS_BRANCH_REGEX` | Optional | Python regex for head ref; default `^fix/issue-\d+$`. |
| `IYNX_STATS_AUTHOR` | Optional | GitHub login to filter as PR author; default = **authenticated user** from `GET /user`. |

**Consistency rule:** If `IYNX_STATS_LABEL` is unset, use `IYNX_PR_LABEL`. If neither is set, the stats command must **fail fast** with a clear message (no silent empty results).

**Label matching:** GitHub search uses the label **name** as in the UI; matching is **exact** for the `label:` qualifier (case and spelling must match the label applied at PR creation).

---

## Orchestrator change

**File:** `src/orchestrator.py` (PR creation script inside Docker).

- Read `IYNX_PR_LABEL` from the host environment and pass it into the container env (alongside existing `GH_TOKEN` / `GITHUB_TOKEN`).
- Append to `gh pr create`: `--label <value>` (shell-quote safely).
- If `IYNX_PR_LABEL` is **unset** or **empty**: **omit** `--label` (preserve today’s behavior for users who do not opt in). Document that **stats filtering by label** requires setting the variable for **new** PRs going forward; old PRs without the label will not appear in label-based stats.

---

## Stats CLI

**Suggested entry:** new module e.g. `src/pr_stats.py` and a thin runner `python -m pr_stats` or `stats.py` at repo root — follow whatever pattern exists after implementation planning (single entry point, documented in README).

### Flags

| Flag | Behavior |
|------|----------|
| `--format json` | See **JSON output contract** below. |
| `--format table` | Plain text rows/columns. |
| `--format card` \| `--format share` | Same Unicode “dashboard” renderer (aliases). |
| `--no-color` | Disable ANSI in `card`/`share`/`table` as applicable. |
| `--label` | Override label (else env chain above). |
| `--branch-regex` | Override branch regex. |
| `--author` | Override author login. |
| `--max` | Optional safety cap on items processed (pagination stop); document default (e.g. none or high ceiling). |

**Exit codes:** `0` success; `1` configuration or usage error; `2` GitHub API error after retries (optional distinction; document).

### JSON output contract (`--format json`)

Stable fields (semver: additive only until v2):

```json
{
  "schema_version": 1,
  "author": "octocat",
  "label": "iynx-fix",
  "branch_pattern_source": "default",
  "counts": {
    "total": 0,
    "merged": 0,
    "open": 0,
    "closed_unmerged": 0
  },
  "by_repo": {
    "owner/name": { "total": 0, "merged": 0, "open": 0, "closed_unmerged": 0 }
  },
  "limits": {
    "search_results_returned": 0,
    "search_truncated": false
  }
}
```

- **`by_repo`:** Omit or `{}` when empty; include when non-empty.
- **`limits.search_truncated`:** Set `true` when GitHub Search returns **1,000** results (the **hard cap** per query). In that case **totals are incomplete**; document in README and print a **warning** on stderr for `table`/`card`/`share`/`json`.

---

## GitHub API strategy

1. **Resolve author login:** `GET /user` unless `--author` / `IYNX_STATS_AUTHOR` is set.
2. **Search:** `GET /search/issues` with query  
   `is:pr author:<login> label:<label>`  
   Paginate (`per_page` 100, follow `Link` header until done or `--max`).

   **GitHub Search hard cap:** Each query returns at most **1,000** total results. If `total_count` from the API is **> 1,000**, set `limits.search_truncated` to `true` and emit a warning; counts reflect only the first 1,000 candidates (still filtered by branch regex). v1 does **not** require sharding queries (e.g. by date or repo); document as a known limitation and optional future `--since` or split strategies.
3. **Enrich:** Search results may not always include full head ref detail in one payload. For each candidate, use **`GET /repos/{owner}/{repo}/pulls/{pull_number}`** or pull from search item if `pull_request` + head ref is reliably present — **implementation plan** should pick one path and document; requirement is **correct head ref** for filtering.
4. **Filter:** Keep items whose **head ref** `ref` (branch name) matches `IYNX_STATS_BRANCH_REGEX`.
5. **Bucket:**
   - `merged` — `merged_at` is non-null.
   - `open` — `state == open`.
   - `closed` (unmerged) — `state == closed` and `merged_at` is null.

**Rate limits:** Search API has low quotas. Implement **pagination** only in v1; on `403` with rate limit or `Retry-After`, sleep and retry (bounded attempts). Document that very large histories may need a **future** `--since` date filter (YAGNI for v1 unless review flags it).

---

## Card / share output

- **Stdlib only:** Unicode box-drawing + optional ANSI; no new required dependencies.
- **Default width:** Target ~**40–56** columns for screenshot readability; optional auto-detect terminal width.
- **Content:** Title (e.g. `iynx · PR stats`), filter one-liner (label + branch pattern), large aligned counts for merged / open / closed / total.
- **`--no-color`:** Plain text for copy-paste or terminals without ANSI. Respect **`NO_COLOR`** (non-empty) the same as `--no-color` for CI and snapshot tests.
- **`NO_COLOR`:** When set, card renderer must not emit ANSI (same as `--no-color`).

---

## Testing

- **Unit tests** with mocked `requests`: search response pages, user endpoint, PR detail if needed; **regex filter** and **state bucketing** covered in isolation.
- **Snapshot or golden string** for `card` output with **ANSI stripped** or fixed `NO_COLOR=1` for stability.
- **Integration** tests optional (no live token in CI); document manual smoke: run CLI against real token with a test label.

---

## Documentation

- **README:** New section “PR statistics”; env vars; examples for `json` and `card`.
- **`.env.example`:** Comment lines for `IYNX_PR_LABEL`, optional stats overrides.

---

## Open points for implementation plan only

- Exact package/module layout and console script name (`python -m …`).
- Whether search items always include enough head ref data or every item needs a follow-up GET (verify against GitHub API response shape in implementation).
