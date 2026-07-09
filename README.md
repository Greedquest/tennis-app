# tennis-app

A Python application for polling tennis court availability and sending email notifications via Gmail.

## Dashboard

A Marimo notebook has been set up to help debug the app.

<a href="https://molab.marimo.io/github/Greedquest/tennis-app/blob/main/dashboard.py/wasm"><img src="https://marimo.io/molab-shield.svg" alt="Open in MoLab"></a>

Run locally with:

```sh
pip install marimo anywidget polars requests
marimo run dashboard.py
```

## Local Wednesday-Evening Court Watch

`scripts/watch_highbury_fields.py` is a standalone local script (not part of
the Gmail poller above) that watches for Highbury Fields / Islington Tennis
Centre (Outdoor) evening slots on [localtenniscourts.com](https://localtenniscourts.com)
and fires a desktop notification the moment a slot at or after 19:00 flips
from booked to free. Alert only — it never books anything.

It's meant to run outside Claude Code (routines are hourly at best; this
needs 5-minute granularity), via cron or a phone automation tool like
Tasker/Termux:

```sh
pip install -r requirements.txt
# every 5 min, Wednesdays only, noon-22:00 (the script also self-checks the window)
*/5 12-21 * * 3 /usr/bin/python3 /path/to/watch_highbury_fields.py
```

Test it immediately without waiting for Wednesday:

```sh
python scripts/watch_highbury_fields.py --force --no-notify
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
