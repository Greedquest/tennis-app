# tennis-app

A Python application for polling tennis court availability and sending email notifications via Gmail.

## Local Wednesday-evening court watch

`scripts/local_court_watch.py` is a separate, standalone script (not the cloud
GitHub Actions poller above) for one specific alert: a slot starting at or
after 19:00 on **Wednesday**, at Islington Tennis Centre (outdoor) or Highbury
Fields, flipping from fully booked to free. It only ever fires a desktop
notification -- it never books anything.

It's meant to run from cron (or Termux's crontab on Android) every 5 minutes,
year-round; the script itself checks that it's Wednesday between midday and
22:00 and no-ops quietly otherwise, so a single cron entry installed once is
enough:

```cron
*/5 * * * * cd /path/to/tennis-app && PYTHONPATH=. python3 scripts/local_court_watch.py >> /tmp/tennis-watch.log 2>&1
```

Only needs `requests` (no `polars`/`redmail`). Notifications try, in order:
Termux (`termux-notification`), macOS (`osascript`), Linux (`notify-send`),
falling back to a printed line if none are available.

To test without hitting the live API or waiting for Wednesday:

```sh
PYTHONPATH=. python scripts/local_court_watch.py --force \
  --fixtures testing/fixtures/late_wed_slot_booked.json --date 2026-07-08 --cache /tmp/watch.json
PYTHONPATH=. python scripts/local_court_watch.py --force \
  --fixtures testing/fixtures/late_wed_slot_free.json --date 2026-07-08 --cache /tmp/watch.json
```

The second run should report the Islington Tennis Centre slot as newly opened.

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
