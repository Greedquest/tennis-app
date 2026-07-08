# tennis-app

A Python application for polling tennis court availability and sending email notifications via Gmail.

## Wednesday-evening court watch (local script)

`scripts/watch_wednesday_courts.py` is a separate, standalone monitor for
[localtenniscourts.com](https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor)
(Highbury Fields / Islington Tennis Centre outdoor). It alerts the moment a
slot starting at or after 19:00 *today* flips from booked to free — alert
only, no booking automation.

It's intentionally not part of the `tennis_app` package or the GitHub
Actions poller above: that poller targets a different site (Better Admin)
on a different schedule, and this task needs 5-minute granularity, which
is finer than a hosted routine can offer. Instead it's meant to run from
your own machine (or a phone via Termux) on a cron-like schedule.

```sh
pip install requests beautifulsoup4
# optional: desktop notification fallback when not running under Termux
pip install plyer

python scripts/watch_wednesday_courts.py --force --dry-run --verbose  # test run
```

Cron (every 5 min on Wednesdays — the script's own time-window check narrows
this to midday–22:00, so the cron expression itself can stay loose):

```
*/5 * * * 3 /usr/bin/python3 /path/to/watch_wednesday_courts.py
```

On Termux, install `cronie` (or drive it from Tasker) and `termux-api` +
the Termux:API app so `termux-notification` is available; the script falls
back to `plyer` (desktop) and then a log line if neither is present.

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
