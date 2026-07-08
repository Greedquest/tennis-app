# Routine: Wednesday-evening court watch

> **Scope:** this file documents ONE recurring task — the scheduled Wednesday-
> evening court-availability monitor. It is not general guidance for the repo.
> If you're here for anything else (dashboard, other venues, refactors, a
> different session), these notes don't apply — don't treat the schedule,
> alert rule, or venue list as constraints on unrelated work.

Target behavior for this routine is to alert when a tennis slot starting
≥19:00 on **Wednesday** flips from booked to free (alert only — no booking).
This is now implemented as a standalone LOCAL script,
`scripts/highbury_wednesday_watch.py` — deliberately not folded into the
cloud poller below, since it needs 5-minute polling on Wednesdays only,
which neither a Claude Code routine (hourly-minimum) nor an always-on
Actions cron can do cheaply. Schedule it yourself (cron / Termux+Tasker);
see the script's docstring.

The cloud poller described below is a separate, older system that still
does generic "any change" diffing for a different venue set (Islington
Tennis Centre indoor/outdoor via the Better Admin API). It has not been
merged with the Wednesday-watch logic — the two coexist.

## What the Wednesday-watch script does

- `scripts/highbury_wednesday_watch.py`: fetches
  `https://localtenniscourts.com/?q=highbury-fields`, finds the column for
  today's date, reads slots ≥19:00, and alerts (desktop/Termux notification)
  the moment one flips from booked → free. First run of the day *does*
  alert on anything already free (no baseline yet that day) — that's
  intentional for a live local watcher, unlike the cloud poller's
  never-alert-on-first-sight rule below.
- State cache: a small JSON file (default `~/.cache/highbury_wednesday_watch.json`)
  keyed by today's date label, so a stale cache from last Wednesday is
  correctly ignored rather than diffed against.
- No email/Slack — uses local desktop/Termux notifications, since this
  runs on the user's own machine, not in CI.

## Cloud poller (separate, older system)

- `.github/workflows/poller.yml`, cron `* * * * *` (every minute).
- Each run: fetch → `tennis_app/pipeline.run()` → email via Gmail SMTP if a watched slot opened up, else log quietly and exit.
- Alerting uses generic change detection (`diff_tables`) and emails on any detected row change — no Wednesday/19:00 filtering.
- Cross-run cache: `actions/cache` (keyed per run_id + prefix restore) holds `cache/state.json`. If it's ever lost, the next run has no baseline and correctly stays silent.
- Secrets the routine needs: `EMAIL_FROM`, `EMAIL_TO`, `APP_PASSWORD` (GH Actions secrets).
- Venues: `islington-tennis-centre` / `tennis-court-indoor` + `tennis-court-outdoor`.

## Venues watched, and why Highbury-only on localtenniscourts.com

- Confirmed via a GitHub Actions probe: `https://localtenniscourts.com/?q=highbury-fields` is a valid, live query (plain SSR HTML, no JSON API — a single `requests.get` returns the fully populated table).
- The brief's combined query (`?q=highbury-fields,islington-tennis-centre-outdoor`) silently ignores the unrecognised second slug — its output is byte-for-byte the same table as the Highbury-only query.
- Querying `?q=islington-tennis-centre-outdoor` alone on this site returns an "Oops!" error page (0 tables) — **it is not a valid slug on localtenniscourts.com**. That venue/court identity only exists in the Better Admin API's own slug space (`islington-tennis-centre` / `tennis-court-outdoor`), which the cloud poller above already covers separately (but without the Wednesday/19:00 filter).
- Net effect: `scripts/highbury_wednesday_watch.py` covers Highbury Fields only. If Wednesday-evening ITC-outdoor alerts via the same filtered logic are wanted, that needs a second script (or a shared module) built against `tennis_app/fetch.py`'s Better Admin client, not localtenniscourts.com.

## Gotchas when working on this routine

- **This sandbox can't reach any of the booking sites** — the agent proxy 403s `better-admin.org.uk`, `bookings.better.org.uk`, and `localtenniscourts.com` (WebFetch/curl 403 all of them). "Site down" is almost always the sandbox, not the site.
- **To test a live fetch, run it on GitHub Actions** (runners have real internet): push a throwaway probe workflow triggered by `push` to the branch (not `workflow_dispatch` — needs the file on default branch), then read the job logs (GitHub Actions UI, `gh run view --log`, or whatever GitHub "get job logs" MCP tool your session exposes — return full content, not just the URL), then delete the probe.
- **Better Admin rate-limits bursts**: ~30 rapid requests → spurious 422s even on known-good combos. Space ~1.5s; keep a known-good control to tell throttling from a bad slug.
- Verify the cloud poller locally without emailing: `PYTHONPATH=. python -m tennis_app --fixtures testing/fixtures/enriched_records.json --cache /tmp/state.json --no-notify` (run twice to exercise the diff path).
- Verify the Wednesday-watch script locally without notifying: `python scripts/highbury_wednesday_watch.py --no-notify --force` (`--force` bypasses the Wednesday-only check; run twice to exercise the diff path).
