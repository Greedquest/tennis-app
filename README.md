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

## Highbury Fields Wednesday-evening court watch

`scripts/highbury_wednesday_watch.py` is a separate, standalone monitor from
the Better Admin poller above. It watches
[localtenniscourts.com](https://localtenniscourts.com/?q=highbury-fields)
for Highbury Fields slots starting at or after 19:00 that flip from booked to
free, on Wednesdays only, and fires a desktop/Termux notification. It does
**not** book anything.

It deliberately runs as a **local scheduled script**, not a cloud routine or
GitHub Actions job: it needs a 5-minute cadence, and hosted routines/CI
schedules are hourly at best. It also needs no browser — the page is fully
server-rendered, so a plain HTTP GET already contains the populated table.

Setup:

```sh
pip install -r scripts/requirements-highbury-watch.txt
```

Verify without sending a notification:

```sh
python scripts/highbury_wednesday_watch.py --no-notify --force
```

(`--force` bypasses the Wednesday-only check so you can test any day; drop it
for real runs. Run it twice back-to-back to see the "no new availability"
path once state is cached.)

Schedule it with cron, every 5 minutes, Wednesdays, midday–22:00:

```cron
*/5 12-22 * * 3 cd /path/to/tennis-app && /usr/bin/python3 scripts/highbury_wednesday_watch.py >> ~/.cache/highbury_watch.log 2>&1
```

On Android via Termux + cron (or Tasker calling `termux-job-scheduler`), the
script auto-detects `termux-notification` for the alert; otherwise it falls
back to `notify-send` (Linux) or `osascript` (macOS).

Notes:
- Only the `highbury-fields` slug resolves on localtenniscourts.com. A
  candidate `islington-tennis-centre-outdoor` slug was tried and returns an
  error page on this site — it is not the same identifier space as the
  Better Admin API the poller above uses, so it isn't wired in here.
- State is cached per-day at `~/.cache/highbury_wednesday_watch.json` (or
  `--state PATH`); delete it to reset.

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
