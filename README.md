# tennis-app

A Python application for polling tennis court availability and sending email notifications via Gmail.

## Dashboard

View court availability on demand in your browser — no server required.

<a href="https://molab.marimo.io/github/Greedquest/tennis-app/blob/main/dashboard.py/wasm"><img src="https://marimo.io/molab-shield.svg" alt="Open in MoLab"></a>

Run locally with:

```sh
pip install marimo anywidget polars requests
marimo run dashboard.py
```

## GitHub Copilot Configuration

This repository includes configuration for GitHub Copilot Cloud Agent to access external domains:

- **`.github/agents/copilot-setup-steps.yml`**: Grants Copilot access to marimo.io domains (molab playground) and tennis court booking APIs. This allows Copilot to:
  - Access and debug the marimo notebook on molab
  - Fetch tennis court availability data
  - Resolve "failed to fetch wire" errors when accessing molab links

## Pre-commit Hooks

This project uses [pre-commit](https://pre-commit.com/) and [pre-commit.ci](https://pre-commit.ci/) for automatic code quality checks and fixes.

### Enabled Hooks

- **pyupgrade**: Automatically upgrade syntax for Python 3.12+
- **black**: Code formatting
- **ruff**: Fast linting (replaces flake8, isort, and more) with auto-fix
- **mypy**: Type checking
- **bandit**: Security vulnerability scanning
- **trailing-whitespace, end-of-file-fixer**: File hygiene

### Pre-commit.ci Integration

Since this project is edited via the GitHub web interface, [pre-commit.ci](https://pre-commit.ci/) is configured to:

- Automatically run all hooks on every commit
- Auto-fix issues and push fixes back to the branch
- Weekly automatic updates of hook versions

All code quality checks run automatically - no local setup required!

### Configuration

- Pre-commit hooks: `.pre-commit-config.yaml`
- Pre-commit.ci settings: `.pre-commit-ci.yaml`
- Tool configurations: `pyproject.toml` (black, ruff, mypy, bandit)
