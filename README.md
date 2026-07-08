# tennis-app

A Python application for polling tennis court availability and sending email notifications via Gmail.

## Wednesday-evening Highbury Fields watch

`scripts/highbury_wednesday_watch.py` is a standalone local script (not part
of the cloud poller) that watches Highbury Fields via
[localtenniscourts.com](https://localtenniscourts.com/?q=highbury-fields)
and fires a desktop/Termux notification the moment a slot starting ≥19:00 on
Wednesday flips from booked to free. Alert only — no booking automation.

```sh
pip install requests beautifulsoup4
python scripts/highbury_wednesday_watch.py --no-notify --force  # local test
```

It needs 5-minute polling on Wednesdays only, so schedule it yourself with
cron / Termux+Tasker (see the script's docstring for a crontab example) —
see `CLAUDE.md` for the full routine notes, including why Islington Tennis
Centre outdoor isn't covered by this script.

## Dashboard

A Marimo notebook has been set up to help debug the app.

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


### Pre-commit.ci Integration

Since this project is edited via the GitHub web interface, [pre-commit.ci](https://pre-commit.ci/) is configured to:

- Automatically run all hooks on every commit of open prs
- Auto-fix issues and push fixes back to the branch
- Weekly automatic updates of hook versions


### Configuration

- Pre-commit hooks: `.pre-commit-config.yaml`
- Pre-commit.ci settings: `.pre-commit-ci.yaml`
- Tool configurations: `pyproject.toml` (black, ruff, mypy, bandit)
