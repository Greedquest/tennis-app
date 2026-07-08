# tennis-app

A Python application for polling tennis court availability and sending email notifications via Gmail.

## Wednesday-evening court watcher (local script)

`scripts/watch_wednesday_ltc.py` is a standalone script — separate from the
`tennis_app` package/GitHub Actions poller below, which watches a different
site. This one watches:

https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor

(an aggregator combining Highbury Fields and Islington Tennis Centre outdoor
into one table) and fires a **desktop notification** the moment a Wednesday
slot starting at or after 19:00 flips from booked to free. Alert only — no
booking automation.

The page is server-rendered, so a plain `requests.get()` returns the full
availability table already populated; no browser/JS is needed.

Run it once to see current state, then again to see the diff:

```sh
pip install requests
python scripts/watch_wednesday_ltc.py --cache cache/ltc_wednesday_state.json
```

Verify against a saved fixture without hitting the network:

```sh
python scripts/watch_wednesday_ltc.py \
    --fixture testing/fixtures/localtenniscourts_sample.html \
    --cache /tmp/ltc_state.json --no-notify
```

It's meant to be driven by cron (or Termux/Tasker) every 5 minutes,
Wednesdays only, roughly midday-22:00 — see the script's docstring for a
sample crontab line. Claude Code routines run hourly at minimum, so this
narrower cadence needs a local scheduler, not a hosted routine.

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
