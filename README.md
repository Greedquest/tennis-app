# tennis-app

A Python application for polling tennis court availability and sending email notifications via Gmail.

## What it monitors

Watches **Wednesday evening** slots (start time ≥ 19:00) at two outdoor sites,
and emails the moment a slot flips from **booked → free** so it can be booked
manually (alert only — no booking automation):

- **Highbury Fields** (outdoor)
- **Islington Tennis Centre** (outdoor)

Data comes from the Better Admin JSON API
(`better-admin.org.uk/api/activities/...`), not scraped HTML.

**Behaviour**

- Polls every 5 minutes on Wednesdays, midday–22:00 (`Europe/London`), via the
  `Poller` GitHub Actions workflow. The cron is a coarse UTC gate; the exact,
  DST-aware window is enforced in `tennis_app.pipeline.within_poll_window`.
- Alerts only on a genuine booked → free transition. A slot seen for the first
  time never alerts (avoids a first-run flood), and free → booked is ignored.
- Logs each check quietly; email fires only when something opens up.

Tunable via env vars (`config.py`): `TARGET_WEEKDAY`, `TARGET_MIN_HOUR`,
`POLL_START_HOUR`, `POLL_END_HOUR`, `TZ_NAME`, `VENUES`.

**Local run**

```sh
pip install -r requirements.txt
# manual test off-schedule, no email:
python -m tennis_app --ignore-window --no-notify
```

**Verifying venue slugs**

The Highbury Fields activity slug is confirmed from CI (this repo's environments
can't reach the booking API). Run the **Probe venue slugs** workflow
(`workflow_dispatch`) — `tennis_app/probe.py` tries candidate slugs and logs
which return live data.

Tests: `python -m pytest testing/test_pipeline.py`.

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
