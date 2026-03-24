# Iynx run workflow

How to **start** the full Iynx pipeline (actually execute `python run.py`), then **supervise** it and **explain** it in plain language (progress, watch commands, failures like **`no_pr`**).

For **manual** contribution work (no orchestrator), use **`issue-fix-workflow.md`**. The orchestrator injects that file into the target repo; it does **not** inject this one.

---

## 1. When the user wants to *run* the workflow — execute it

If they say **run Iynx**, **start the workflow**, **run discovery**, **run `python run.py`**, or equivalent, you must **run the process**, not only read `.iynx-run-progress.jsonl` or describe what would happen.

1. **`cd`** to the **Iynx repo root** (directory that contains **`run.py`**, **`Dockerfile`**, **`skills/`**).
2. **Check prerequisites** before starting:
   - **`CURSOR_API_KEY`** set (in `.env` beside `run.py` or in the environment). Without it the host exits **1** immediately.
   - **`GITHUB_TOKEN`** set for real discovery and PR work (strongly recommended).
   - Docker daemon running; image **`iynx-agent:latest`** built (`docker build -t iynx-agent:latest .` from that root if missing).
3. **Run** the entrypoint:
   - Full pipeline **with discovery:** `python run.py`
   - **One repo** (no discovery): `python run.py owner/repo` or `python run.py owner/repo 849`
4. **Long runs:** This can take **tens of minutes to an hour+** (Docker + Cursor phases). If your environment allows **background** execution for long commands, start it in the **background** and tell the user it is running; otherwise run foreground and warn that the session will stay busy. **Do not** skip starting the workflow because it is slow—start it, then use §§3–6 to report status.
5. After it starts, confirm in your reply: **what ran** (command + discovery vs explicit target), and **how to watch** (§4).

You can also pass the same targets via **`IYNX_TARGET_REPO`** and optional **`IYNX_TARGET_ISSUE`** instead of argv. Default `python run.py` runs **discovery** (GitHub issue search → filters → **random** repo), then the Docker/Cursor/PR pipeline.

---

## 2. What actually runs (for the user-facing sentence)

The Iynx agent workflow is **`python run.py`** from that root. Details and env setup: **README → Usage**.

When you tell the user what ran, say it plainly—e.g. *“The Iynx agent workflow is `python run.py` (see README under Usage).”* Note **foreground** vs **background** if you know.

---

## 3. “Progress so far” — how to describe it

Read **`.iynx-run-progress.jsonl`** at the **Iynx project root** (gitignored). Each line is one JSON object: `phase`, `status`, `repo`, `issue`, `detail`, `run_id`, `exit_code`, etc. Use **`IYNX_PROGRESS_JSONL`** only if the user overrode the path.

Build the narrative in this order (skip lines the user’s run has not reached yet):

1. **Discovery** (only when there was no explicit `owner/repo`): Find the row with `phase` **`discovery`**. If `status` is **`completed`**, `detail` is usually the **number of repos** after filters (string). Say e.g. *“Discovery: 29 repos after filters.”* If `status` is **`skipped`** and `detail` is **`no_repos`**, the run stopped early—**no clone**—and will hit **`run_complete`** with **`no_pr`**.
2. **Selected repo:** The host logs something like *“Selected owner/repo (random of N qualifying)”*; the JSONL rows for **`clone`** onward carry **`repo`**: **`owner/repo`**. Say e.g. *“Selected repo: judgemind/judgemind (random pick).”*
3. **Preflight:** Row **`preflight`**. **`completed`** → *“Preflight: passed (open issues exist)”* or, with an issue override, that the issue was validated. **`failed`** → read `detail` (e.g. no open issues, bad issue number) and say the run **did not clone**.
4. **Clone:** **`clone`** **`completed`** → *“Clone: finished (repo cloned in Docker).”*
5. **Bootstrap:** **`bootstrap`** **`completed`** → fold into *“Clone / bootstrap: done”* if you want a short status.
6. **Cursor phases** — use **friendly names** in the user-facing summary; tie them to JSONL `phase` values:

| Say this | JSONL `phase` |
|----------|----------------|
| Phase 1 (context) | `phase1_context` |
| Phase 2 (issue pick) | `phase2_issue_pick` |
| Phase 3 (implement) | `phase3_implement` |
| Phase 4 (PR draft) | `phase4_pr_draft` |
| PR create | `pr_create` |

For each: **`started`** / **`completed`** / **`failed`**. If **`phase3_implement`** is **`started`** or only **`phase1`/`phase2`** are **`completed`**, say clearly what is **still in progress** (e.g. *“Phase 3 (implement) in progress — issue #1545”* when `issue` is present on the row).

7. **Still running:** If there is **no** row with `phase` **`run_complete`** yet, the run is **not** finished. Mention that **phase4**, **pr_create**, and **run_complete** are still to come, or whichever is next.

8. **Duration:** Long runs are normal. Per Docker step, the default timeout is **large** (on the order of **3600s** unless changed—see **`IYNX_DOCKER_RUN_TIMEOUT`** in §8).

---

## 4. “How to watch it” — tell the user

- **Console:** Same session’s log stream; lines tagged **`[docker]`** and **`[iynx]`** mirror progress.
- **Structured file:** Full path to **`.iynx-run-progress.jsonl`** (project root); each line is JSON; **final** lifecycle row is **`run_complete`** when the process is done.
- **PowerShell:** `Get-Content .iynx-run-progress.jsonl -Wait`
- **Unix:** `tail -f .iynx-run-progress.jsonl`

Optional: mention **`run_id`** from a recent JSON line so multiple runs are distinguishable.

---

## 5. Status updates while running

A **table** is easy to scan:

| Step | Status |
|------|--------|
| Discovery | Done — N repos *(or skipped / not applicable if explicit target)* |
| Preflight | Done — `owner/repo` |
| Clone / bootstrap | Done |
| Phase 1 (context) | Done |
| Phase 2 (issue pick) | Done |
| Phase 3 (implement) | In progress — issue #N *(or Done)* |

If **`phase4_pr_draft`**, **`pr_create`**, or **`run_complete`** are **missing**, say the agent **has not** finished implementation or **opened a PR** yet.

Mention **process** if known: e.g. still running, approximate elapsed time from logs.

---

## 6. When the run finishes

Read the last **`run_complete`** row:

- **`detail`:** **`pr_created`** vs **`no_pr`**
- **`exit_code`:** aligns with the process (**0** = PR created, **2** = finished without PR, **1** = fatal host config such as missing **`CURSOR_API_KEY`**)

**If the user sees exit 2 and `no_pr` but phases mostly succeeded**, do **not** stop at “no PR.” Scan JSONL (and stderr/log) for the **last failing step**, often **`pr_create`** with `status` **`failed`** and `exit_code` on that row.

### Example: PR not created because of a label

Orchestrator passes **`IYNX_PR_LABEL`** into `gh pr create`. If that label **does not exist** on the **upstream** repo, `gh` fails with something like *`could not add label: 'lynx' not found`*.

**What to tell the user:**

- What **succeeded** (e.g. repo, issue, phases through implement/draft, branch pushed to fork—if logs show that).
- **Why no PR:** `pr_create` failed; quote or paraphrase the **`gh`** error.
- **What they can do:** Create the label on the upstream repo (if they control it), **or** unset / change **`IYNX_PR_LABEL`** in `.env` and re-run, **or** open the PR manually from GitHub’s “compare / new PR” flow for the pushed branch.

Always tie **actionable** steps to the **actual** error text you see.

---

## 7. Polling (supervising agents)

Do **not** assume `python run.py` finishes quickly. If you are checking on a run, **poll** **`.iynx-run-progress.jsonl`** on the order of **every 60 seconds** (or as the user asks), reading **new** lines since the last check—not a tight loop.

---

## 8. Short reference (implementation details)

Use this when you need exact behavior, not when writing a user-facing status blurb.

**Discovery (default `python run.py`):** GitHub **issue search** per language (**JavaScript, TypeScript, Python**), pool capped by **`DISCOVERY_POOL_SIZE`** (see `src/orchestrator.py`). Filters: **CONTRIBUTING** expected; optionally **skip repos where the token’s user already has PRs**. One repo chosen with **`random.choice`**. Tuning is via **constants** in **`orchestrator.py`**, not env vars.

**Explicit target:** **`IYNX_TARGET_REPO`** or `python run.py owner/repo [issue]` → **discovery skipped**; **`target_resolve`** in JSONL.

**Pipeline order:** `preflight` → `clone` → `bootstrap` → `phase1_context` → `phase2_issue_pick` (skipped when issue fixed upfront) → `phase3_implement` → `verify_tests` (often **skipped**; **`VERIFY_TESTS_AFTER_FIX`** default **false** in code) → `phase4_pr_draft` → `pr_create` → **`run_complete`**.

**Exit codes:** **0** = PR created; **1** = fatal host misconfiguration; **2** = ended without PR.

**Env (common):** `CURSOR_API_KEY` (required), `GITHUB_TOKEN`, `IYNX_TARGET_REPO`, `IYNX_TARGET_ISSUE`, `IYNX_PROGRESS_JSONL`, `IYNX_DOCKER_RUN_TIMEOUT`, `IYNX_PR_LABEL`, `IYNX_DOCKER_TRACE`, `IYNX_CURSOR_MODEL`, … — full list in **`README`** / **`src/orchestrator.py`**.

**Clones:** Under **`workspace/`** at the Iynx root.

**Follow-up on an existing PR:** **`issue-fix-workflow.md`** (PR review section) and **`pr_review.py`**.

**Source files:** `run.py`, `src/orchestrator.py`, `src/discovery.py`.
