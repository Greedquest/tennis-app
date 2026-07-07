# Routine: Wednesday-evening court watch

> **Scope:** this file documents ONE recurring task — the scheduled Wednesday-
> evening court-availability monitor. It is not general guidance for the repo.
> If you're here for anything else (dashboard, other venues, refactors, a
> different session), these notes don't apply — don't treat the schedule,
> alert rule, or venue list as constraints on unrelated work.

Alert the moment a tennis slot starting ≥19:00 on **Wednesday** flips from
booked to free. Alert only — no booking. Everything below is what this routine
needs; ignore general dev notes.

## What the routine does

- Poller: `.github/workflows/poller.yml`, cron `*/5 11-22 * * 3` (every 5 min, Wed only, ~midday–22:00 UK). GH Actions cron is UTC/no-DST, so 11–22 UTC pads for both BST and GMT.
- Each run: fetch → `tennis_app/pipeline.run()` → email via Gmail SMTP if a watched slot opened up, else log quietly and exit.
- Alert fires ONLY on a `Spaces` <=0 → >0 transition between polls, inside the window. First-ever sighting of a slot never alerts (no baseline). Nothing else emails.
- Window config: `WATCH_WEEKDAY=3`, `WATCH_HOUR_FROM=19` in `tennis_app/config.py`. Logic: `filter_watch_window` / `newly_available_slots` in `tennis_app/transform.py`.
- Cross-run cache: `actions/cache` (keyed per run_id + prefix restore) holds `cache/state.json`. If it's ever lost, the next run has no baseline and correctly stays silent.
- Secrets the routine needs: `EMAIL_FROM`, `EMAIL_TO`, `APP_PASSWORD` (GH Actions secrets).

## Venues watched

- `islington-tennis-centre` / `tennis-court-indoor` + `tennis-court-outdoor`.
- Highbury Fields = venue `islington-parks`, court `tennis-court-outdoor`.
  ⚠️ Slug is structurally valid (HTTP 200) but returned **0 records** on every
  probed date — not yet confirmed to carry live data. Check a real Wednesday
  run's logs before trusting Highbury alerts.

## Gotchas when working on this routine

- **This sandbox can't reach the booking API** — the agent proxy 403s `better-admin.org.uk` / `bookings.better.org.uk` (WebFetch 403s everything). "API down" is almost always the sandbox, not the API.
- **To test the live fetch, run it on GitHub Actions** (runners have real internet): push a throwaway probe workflow triggered by `push` to the branch (not `workflow_dispatch` — needs the file on default branch), read logs via `mcp__github__get_job_logs` (`return_content: true`), then delete the probe.
- **Better Admin rate-limits bursts**: ~30 rapid requests → spurious 422s even on known-good combos. Space ~1.5s; keep a known-good control to tell throttling from a bad slug.
- Verify locally without emailing: `PYTHONPATH=. python -m tennis_app --fixtures testing/fixtures/enriched_records.json --cache /tmp/state.json --no-notify` (run twice to exercise the diff path).
