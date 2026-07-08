# Routine: Wednesday-evening court watch

> **Scope:** this file documents ONE recurring task — the scheduled Wednesday-
> evening court-availability monitor. It is not general guidance for the repo.
> If you're here for anything else (dashboard, other venues, refactors, a
> different session), these notes don't apply — don't treat the schedule,
> alert rule, or venue list as constraints on unrelated work.

Target behavior for this routine is to alert when a tennis slot starting
≥19:00 on **Wednesday** flips from booked to free (alert only — no booking).
This has landed: `tennis_app.transform.filter_watch_window` +
`newly_available_slots` implement the rule; `pipeline.run()` uses them instead
of generic change detection.

## What the routine does

- Poller: `.github/workflows/poller.yml`, cron `*/5 11-22 * * 3` — every 5
  minutes, Wednesdays only, 11:00-22:55 UTC (covers noon-22:00 local across
  both GMT and BST without DST-aware cron).
- Each run: fetch → `tennis_app/pipeline.run()` → email via Gmail SMTP if a
  watched slot opened up, else log quietly and exit.
- Alerting: `newly_available_slots()` only fires on `Spaces` transitions from
  `<=0` (booked) to `>0` (free) within the watch window
  (`WATCH_WEEKDAY`/`WATCH_HOUR_FROM` in `config.py`, default Wed/19). First-time
  sightings of a slot are ignored (no baseline to compare).
- Cross-run cache: `actions/cache` (keyed per run_id + prefix restore) holds `cache/state.json`. If it's ever lost, the next run has no baseline and correctly stays silent.
- Secrets the routine needs: `EMAIL_FROM`, `EMAIL_TO`, `APP_PASSWORD` (GH Actions secrets).
- Local alternative: `scripts/watch_local.py` runs the same fetch/filter logic
  on a schedule of your own (cron/Termux) and fires a desktop notification
  instead of email — for when you'd rather not touch GH Actions secrets.

## Venues watched

- `islington-tennis-centre` / `tennis-court-indoor` + `tennis-court-outdoor`.
- Highbury Fields is `islington-tennis-centre` / `highbury-tennis` (confirmed
  via localtenniscourts.com's SSR-embedded `booking_url` payload — it's the
  same Better Admin backend, just a different `court` slug under the same
  `venue`. Not `islington-parks`, which was an earlier unconfirmed guess).

## Gotchas when working on this routine

- **This sandbox can't reach the booking API** — the agent proxy 403s `better-admin.org.uk` / `bookings.better.org.uk` (WebFetch 403s everything). "API down" is almost always the sandbox, not the API.
- **To test the live fetch, run it on GitHub Actions** (runners have real internet): push a throwaway probe workflow triggered by `push` to the branch (not `workflow_dispatch` — needs the file on default branch), then read the job logs (GitHub Actions UI, `gh run view --log`, or whatever GitHub "get job logs" MCP tool your session exposes — return full content, not just the URL), then delete the probe.
- **Better Admin rate-limits bursts**: ~30 rapid requests → spurious 422s even on known-good combos. Space ~1.5s; keep a known-good control to tell throttling from a bad slug.
- Verify locally without emailing: `PYTHONPATH=. python -m tennis_app --fixtures testing/fixtures/enriched_records.json --cache /tmp/state.json --no-notify` (run twice to exercise the diff path).
