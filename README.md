# tennis-app

A Python application for polling tennis court availability and sending email notifications via Gmail.

## Wednesday-evening court watch (local script, not the cloud poller)

`scripts/wednesday_watch.py` alerts the moment a tennis slot starting at or
after 19:00 on Wednesday flips from booked to free, for Highbury Fields and
Islington Tennis Centre (outdoor). It's alert-only — nothing is booked
automatically.

This deliberately does **not** run as a cloud routine or GitHub Actions
schedule: those are hourly-minimum, too coarse for a 5-minute check. Run it
locally instead, either via cron:

```sh
# crontab -e — Wednesdays only, midday to 22:00, every 5 minutes
*/5 12-21 * * 3 cd /path/to/tennis-app && python3 scripts/wednesday_watch.py >> logs/wednesday_watch.log 2>&1
0   22    * * 3 cd /path/to/tennis-app && python3 scripts/wednesday_watch.py >> logs/wednesday_watch.log 2>&1
```

or as an always-on loop that sleeps between checks and only polls during the
Wednesday window:

```sh
python3 scripts/wednesday_watch.py --loop
```

On Termux (Android), `pkg install cronie termux-api` gives you the same
crontab lines plus `termux-notification` alerts; the script also falls back
to `notify-send` (Linux desktop) or `osascript` (macOS) automatically.

Verify without waiting for a real Wednesday by faking the state file: run
twice with `--state /tmp/test-state.json`, editing the spaces count between
runs to simulate a booked→free flip.

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
