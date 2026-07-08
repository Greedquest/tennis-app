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

## Wednesday-evening court watch (local script)

`scripts/wednesday_watch.py` is a standalone monitor for
[localtenniscourts.com](https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor)
(Highbury Fields + Islington Tennis Centre outdoor, combined). It alerts via
desktop notification the moment a **Wednesday** slot starting at or after
**19:00** flips from booked to free. Alert only -- no booking automation.

This is deliberately separate from the `tennis_app` cloud poller above:
localtenniscourts.com has no JSON API (its availability table is
server-rendered HTML, parsed directly with `requests` + regex -- no browser
needed), and the alert is a desktop notification, which only makes sense
running locally. The required cadence (every 5 minutes, Wednesdays
midday-22:00) is also finer-grained than Claude Code cloud routines support,
so run it via your own cron / Tasker, not as a hosted job:

```sh
pip install requests
# crontab -e
*/5 12-21 * * 3 /usr/bin/python3 /path/to/scripts/wednesday_watch.py
```

Dry-run against a saved page (no network, no notification):

```sh
python scripts/wednesday_watch.py --html-fixture testing/fixtures/ltc_sample.html --no-notify
python scripts/wednesday_watch.py --html-fixture testing/fixtures/ltc_sample_wed_free.html --no-notify
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
