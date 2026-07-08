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

## Local Wednesday-evening court watch

`scripts/local_court_watch.py` is a separate, standalone monitor — not part
of the `tennis_app` GitHub Actions poller above. It watches
[localtenniscourts.com](https://localtenniscourts.com) (an aggregator that
re-serves Highbury Fields and Islington Tennis Centre - Outdoor availability)
and fires a desktop notification the moment a slot starting at or after
19:00 on a Wednesday flips from booked to free. Booking stays manual — this
only alerts.

It's meant to run from a *local* scheduler (cron, or Termux + Tasker on
Android), every 5 minutes, Wednesdays from midday to 22:00 — Claude Code
routines are hourly-minimum, too coarse for this. The script re-checks the
day/time itself, so a coarser cron trigger is safe too:

```sh
*/5 12-21 * * 3 cd /path/to/tennis-app && python3 scripts/local_court_watch.py
```

Verify locally without hitting the network:

```sh
python scripts/local_court_watch.py \
  --fixture testing/fixtures/localtenniscourts_sample.html \
  --cache /tmp/local_court_watch_state.json --dry-run --force
```

The site embeds its data in the page as a serialized JS reference graph
rather than a plain JSON API; see the parsing notes at the top of the
script, and `scripts/probe_localtenniscourts.py` for how to re-verify the
page structure if it ever changes (run it from a GitHub Actions job — the
domain isn't reachable from every sandbox).

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
