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

## Wednesday-evening court watch (local, 5-minute polling)

`scripts/wednesday_watch.py` is a standalone, local alert-only monitor —
distinct from the cloud poller above. It's meant for tighter polling
(every 5 minutes) restricted to Wednesday afternoons/evenings, which
doesn't fit a cloud-hosted routine (those run hourly at best). Run it from
a local machine or phone (e.g. Termux) via cron, not from CI.

It checks the same venues as `tennis_app/config.py`
(`islington-tennis-centre`, indoor + outdoor) for Wednesday slots starting
at or after 19:00, and fires a desktop/phone notification only when a slot
flips from 0 spaces to >0 spaces since the last run — never on any other
change, and never on a slot it has no baseline for yet (so the very first
run is always quiet). It never books anything.

Highbury Fields (`islington-parks`) is intentionally left out: its exact
venue/court slug isn't confirmed yet (see `scripts/probe_venue.py` and the
gotchas below) — the two candidates tried both return `200` with zero
records, which doesn't distinguish "right slug, nothing free right now"
from "wrong slug". Add it to the `VENUES` list in `wednesday_watch.py`
once confirmed.

Run manually:

```sh
PYTHONPATH=. python scripts/wednesday_watch.py --no-notify  # dry run, prints instead of alerting
PYTHONPATH=. python scripts/wednesday_watch.py               # real run, sends a notification on a flip
```

Notifications try, in order: [`plyer`](https://pypi.org/project/plyer/)
(cross-platform, `pip install plyer`), `termux-notification` (Termux +
Termux:API on Android), `notify-send` (Linux), `osascript` (macOS) —
falling back to a log line if none are available.

Example crontab entry (every 5 minutes, Wednesdays, 12:00-22:00 local time):

```cron
*/5 12-21 * * 3 cd /path/to/tennis-app && PYTHONPATH=. python scripts/wednesday_watch.py >> /tmp/wednesday-watch.log 2>&1
```

(`12-21` covers the 12:00-22:00 window since cron hour ranges are
inclusive of the start of each hour; the last check in the window fires at
21:55.) On Termux, install `cronie` (or use `termux-job-scheduler`) and add
the same line via `crontab -e`. For Tasker, use a time-span + day-of-week
profile that shells out to the same command instead of cron.

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
