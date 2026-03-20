# The Fixer — GitHub Contribution Agent

An autonomous agent that discovers trendy GitHub repos, learns contribution guidelines, fixes issues, tests in Docker, and opens PRs. Uses **Cursor CLI** as the primary AI engine. All repo execution (clone, npm test, etc.) runs **inside Docker** for safety.

## Architecture

- **Host**: Runs discovery (GitHub API), Docker commands, and writes bootstrap/config. Never executes repo code.
- **Docker**: Cursor CLI, gh, git. Clone, fix, test, and PR creation happen inside the container.

## Cursor IDE: Superpowers (optional)

[Superpowers](https://github.com/obra/superpowers) adds shared agent skills (TDD, planning, debugging workflows). In Cursor Agent chat you can run `/add-plugin superpowers` or install **Superpowers** from the marketplace.

For a **local install** (same layout Cursor expects under `~/.cursor/plugins/local`), clone the repo and reload the editor:

```powershell
# Windows (PowerShell)
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.cursor\plugins\local" | Out-Null
git clone --depth 1 https://github.com/obra/superpowers.git "$env:USERPROFILE\.cursor\plugins\local\superpowers"
```

```bash
# macOS / Linux
mkdir -p ~/.cursor/plugins/local
git clone --depth 1 https://github.com/obra/superpowers.git ~/.cursor/plugins/local/superpowers
```

Then **Developer: Reload Window** so rules/skills load. Update with `git pull` inside that clone.

## Prerequisites

- Docker
- Python 3.10+
- [Cursor CLI](https://cursor.com/docs/cli/overview) (installed in the image)
- `CURSOR_API_KEY` (from [Cursor settings](https://cursor.com/settings))
- `GITHUB_TOKEN` with `repo` scope (for discovery and PR creation)

## Setup

```bash
# Clone and enter project
cd the-fixer

# Create venv and install deps
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS

pip install -r requirements.txt

# Run unit tests (no Docker)
pytest tests/ -v

# With coverage (threshold in pyproject.toml)
pytest tests/ -v --cov=src --cov-report=term-missing

# Lint / format (Ruff)
ruff check src tests run.py
ruff format src tests run.py

# Copy env template and fill in secrets
copy .env.example .env
# Edit .env with CURSOR_API_KEY and GITHUB_TOKEN

# Build Docker image
docker build -t the-fixer-agent:latest .
```

## Usage

```bash
# Load env
set -a && source .env && set +a   # Linux/macOS
# Or on Windows: $env:CURSOR_API_KEY="..."; $env:GITHUB_TOKEN="..."

# Run the agent (discovers repos, fixes one issue, opens PR)
python run.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CURSOR_API_KEY` | Yes | Cursor CLI API key |
| `GITHUB_TOKEN` | Yes* | GitHub token (repo scope) for discovery and PRs |
| `FIXER_REPO_LIMIT` | No | Max repos to fetch (default: 5) |
| `FIXER_ONE_PR_PER_RUN` | No | Stop after first PR (default: 1) |
| `FIXER_CURSOR_MODEL` | No | Cursor CLI model (default: `composer-2`). List models: `docker run --rm --entrypoint cursor-agent the-fixer-agent:latest --list-models` |

*Without `GITHUB_TOKEN`, discovery is rate-limited (60 req/hr) and PR creation will fail.

## Project Structure

```
the-fixer/
├── Dockerfile           # Cursor CLI + gh + git + jq
├── docker-compose.yml   # Optional local dev
├── src/
│   ├── orchestrator.py  # Main loop
│   ├── discovery.py     # GitHub Search API
│   ├── github_repo_checks.py  # CONTRIBUTING + author PR checks
│   ├── bootstrap.py    # Generate .cursor-agent per repo
│   └── pr.py           # Fork + push + gh pr create
├── skills/
│   └── issue-fix-workflow.md
├── tests/               # pytest (discovery + GitHub checks)
├── workspace/           # Mount point (gitignored)
├── .env.example
└── README.md
```

## Flow

1. **Discovery**: Search repos with `stars:>FIXER_MIN_STARS` and `created:>…` (default last 30 days), paginate a pool, then keep only repos with a CONTRIBUTING file (GitHub API) and none of your prior PRs to that repo (optional).
2. **Clone**: `git clone` inside Docker into `workspace/owner-repo/`.
3. **Bootstrap**: Generate `fixer.cursor-agent` from repo structure (Node/Python/Rust).
4. **Phase 1**: Cursor writes `.fixer/summary.md` and `.fixer/context.json` (`test_command`, `lint_command`) from the contribution guide.
5. **Phase 2**: Cursor picks a `good first issue` / `help wanted` issue.
6. **Phase 3**: Cursor implements the fix using the summary, runs tests, does not commit `.fixer/`.
7. **Verify** (optional): If `FIXER_VERIFY_TESTS=1`, Docker re-runs `test_command` from `context.json`.
8. **Phase 4**: Cursor writes `.fixer/pr-draft.json` (`title`, `body`).
9. **PR**: Host writes `.fixer/pr-body.md`; `gh repo fork`, push, `gh pr create --body-file …`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests, and PR guidelines.

## Security

Report security issues as described in [SECURITY.md](SECURITY.md).

## Safety

- Never run `npm install`, `pytest`, or any repo scripts on the host.
- All clone, fix, and test execution happens inside the Docker container.
- The host only performs HTTP (discovery), Docker commands, and file writes.
