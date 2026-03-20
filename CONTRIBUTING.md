# Contributing

Thanks for helping improve The Fixer. This project runs untrusted upstream code only inside Docker; keep that invariant in mind when changing behavior.

## Development setup

- Python **3.10+**
- Optional: **Docker** for full agent runs (see README)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your keys locally. **Never commit `.env`** or paste real tokens into issues or PRs.

## Tests

Run the unit tests (no Docker required):

```bash
pytest tests/ -v
```

Coverage (uses `pyproject.toml` thresholds; requires `pytest-cov` from `requirements.txt`):

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

Lint and format ([Ruff](https://docs.astral.sh/ruff/); config in `pyproject.toml`):

```bash
ruff check src tests run.py
ruff format --check src tests run.py   # verify formatting; omit --check to auto-format
```

Add or update tests when you change behavior in `src/`.

## Pull requests

- Keep changes focused on one concern.
- Match existing style and patterns in the files you touch.
- Describe the problem and your approach in the PR description.

## Security

Report security issues privately as described in [SECURITY.md](SECURITY.md).
