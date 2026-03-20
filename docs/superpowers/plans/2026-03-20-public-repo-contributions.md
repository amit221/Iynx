# Public repository & contributions readiness

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish this project as a public GitHub repository with clear licensing, contribution expectations, and no leaked secrets so others can fork, open issues, and submit PRs safely.

**Architecture:** Treat “open sourcing” as a small set of repo artifacts (license, contributor docs, ignore rules) plus GitHub hosting settings. Code changes are minimal; most work is documentation, `git` initialization, and a one-time push and visibility change on GitHub.

**Tech Stack:** Git, GitHub, Markdown, Python/pytest (for optional CI), PowerShell or bash for local commands.

---

## File structure (created or modified)

| Path | Role |
|------|------|
| `LICENSE` | Legal terms for use and contribution (choose SPDX license with maintainer). |
| `CONTRIBUTING.md` | How to set up venv, run tests, open PRs, scope of acceptable changes. |
| `SECURITY.md` | How to report vulnerabilities privately (GitHub reads this for Security tab). |
| `.gitignore` | Ensure caches, venv, secrets, and `workspace/` stay out of history. |
| `README.md` | Short “Contributing” section linking to `CONTRIBUTING.md`. |
| `.github/workflows/ci.yml` (optional) | Run `pytest` on push/PR. |

---

### Task 1: Secret and hygiene audit (before any remote)

**Files:**
- Review: entire tree except `.venv/`, `workspace/`
- Modify: none unless secrets found

- [ ] **Step 1: Search for accidental secrets**

Run from repo root (PowerShell):

```powershell
Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch '\\\.venv\\|\\workspace\\' } |
  Select-String -Pattern 'CURSOR_API_KEY|GITHUB_TOKEN|ghp_[A-Za-z0-9]+|sk-[A-Za-z0-9]+' -List
```

Expected: no matches in tracked source; if matches appear, remove or redact before committing.

- [ ] **Step 2: Confirm `.env` is never committed**

Run: `git check-ignore -v .env` (after `git init` in Task 5).  
Expected: `.gitignore` rule listing `.env`.

---

### Task 2: Harden `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append common local artifacts**

Add lines (if not already present):

```
.pytest_cache/
.mypy_cache/
.ruff_cache/
.DS_Store
Thumbs.db
.idea/
.vscode/
```

- [ ] **Step 2: Commit in Task 5 together with other files**

Reason: keeps contributor PRs clean and avoids cache noise in diffs.

---

### Task 3: Add an open-source license

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: Choose a license**

Pick one (maintainer decision): e.g. **MIT** (permissive) or **Apache-2.0** (patent grant). Do not leave the repo public without a license if you want others to know they may use the code.

- [ ] **Step 2: Add the standard license text**

Use GitHub’s license templates or [choosealicense.com](https://choosealicense.com/). Replace `[year]` and `[copyright holder]` with real values.

---

### Task 4: Add `CONTRIBUTING.md`

**Files:**
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Document local workflow**

Include at minimum:

- Python 3.10+, venv, `pip install -r requirements.txt`
- `pytest tests/ -v` before PRs
- Docker image build optional for full integration
- Never commit `.env` or real tokens; use `.env.example` only
- Small, focused PRs; link to any code style already used in `src/`

- [ ] **Step 2: PR expectations**

State that changes should match existing patterns, include tests when behavior changes, and describe the problem/solution in the PR body.

---

### Task 5: Add `SECURITY.md` (recommended for public repos)

**Files:**
- Create: `SECURITY.md`

- [ ] **Step 1: Use GitHub’s security policy template**

Include: preferred contact (email or GitHub Security Advisories), what versions are supported, and that public disclosure should wait for a maintainer response window (e.g. 90 days) unless agreed otherwise.

---

### Task 6: Link from `README.md`

**Files:**
- Modify: `README.md` (add a short section near the end)

- [ ] **Step 1: Add “Contributing” and “Security” bullets**

Example (adjust wording to taste):

```markdown
## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests, and PR guidelines.

## Security

Please report security issues as described in [SECURITY.md](SECURITY.md).
```

---

### Task 7: Initialize Git and first commit

**Files:**
- Create: `.git/` (via git)

- [ ] **Step 1: Initialize repository**

Run (PowerShell):

```powershell
Set-Location "c:\Users\97254\the-fixer"
git init
git add .
git status
```

Expected: `status` shows staged files; **must not** list `.env`, `.venv/`, `workspace/`, or `.pytest_cache/`.

- [ ] **Step 2: First commit**

```powershell
git commit -m "chore: initial public project import"
```

---

### Task 8: Create GitHub repository and push

**Files:**
- None (GitHub UI or `gh`)

- [ ] **Step 1: Create empty repo on GitHub**

Name e.g. `the-fixer`. Do **not** add README/license on GitHub if you already have them locally (avoids merge conflicts). Prefer starting empty.

- [ ] **Step 2: Add remote and push**

```powershell
git remote add origin https://github.com/<your-user>/<repo>.git
git branch -M main
git push -u origin main
```

Expected: push succeeds; default branch is `main`.

---

### Task 9: Make repository public and enable collaboration

**Files:**
- None (GitHub settings)

- [ ] **Step 1: Change visibility to Public**

Repository **Settings → General → Danger Zone → Change repository visibility → Public**. Confirm implications (forks, indexing).

- [ ] **Step 2: Enable community features**

Settings: ensure **Issues** (and optionally **Discussions**) are on. Add **description**, **topics**, and **website** if you have them.

- [ ] **Step 3: Branch protection (optional, later)**

Protect `main`: require PR reviews or status checks once CI exists.

---

### Task 10 (optional): GitHub Actions CI for pytest

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Add workflow**

Minimal workflow: trigger on `push` and `pull_request` to `main`, `ubuntu-latest`, Python 3.10–3.12 matrix or single version, `pip install -r requirements.txt`, `pytest tests/ -v`.

- [ ] **Step 2: Push and verify**

Open a test PR or push to `main`; confirm green check on the Actions tab.

---

## Execution handoff

**Plan complete and saved to** `docs/superpowers/plans/2026-03-20-public-repo-contributions.md`.

**Two execution options:**

1. **Subagent-driven (recommended)** — Use @superpowers:subagent-driven-development: fresh subagent per task, review between tasks.

2. **Inline execution** — Use @superpowers:executing-plans in this session with checkpoints.

**Which approach do you want?**

---

## References

- @superpowers:writing-plans — plan format and review loop
- [GitHub: Licensing a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)
- [GitHub: Setting repository visibility](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
