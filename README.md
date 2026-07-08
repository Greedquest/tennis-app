# tennis-app

A Python application for polling tennis court availability and sending email notifications via Gmail.

## Local Wednesday-evening court watch (localtenniscourts.com)

`scripts/local_court_watch.py` is a separate, standalone monitor for a different
source: [localtenniscourts.com](https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor),
which aggregates Highbury Fields and Islington Tennis Centre (outdoor) into one
search. It alerts (desktop notification only, no booking) the moment a slot
starting at or after 19:00 on Wednesday flips from booked to free.

The site has no JSON API — the availability grid is fully server-rendered into
the initial HTML, so the script does a plain HTTP GET and parses the table
with BeautifulSoup.

This is intentionally **not** a GitHub Actions / Claude Code cloud routine:
cloud routines run hourly at best, and this needs a 5-minute cadence during a
narrow window. Run it yourself with cron or Termux:

```sh
pip install requests beautifulsoup4

# Every 5 minutes, Wednesdays only, midday to 22:00
*/5 12-21 * * 3 cd /path/to/tennis-app && python3 scripts/local_court_watch.py
```

On Termux (Android), install `termux-api` for `termux-notification` support,
then add the same line via `crontab -e` (needs `cronie`/`termux-services`) or
a Tasker task that shells out on the same schedule.

Test the parser offline against a saved page snapshot (no network needed):

```sh
python3 scripts/local_court_watch.py \
  --html-file testing/fixtures/localtenniscourts_sample.html \
  --state-file /tmp/state.json --no-notify
```

State (last-seen court count per Wednesday time slot) is cached at
`~/.cache/tennis-watch/state.json` by default (override with `--state-file`).

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
