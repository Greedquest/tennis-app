# Routine: Wednesday-evening court watch

> **Scope:** this file documents ONE recurring task — the scheduled Wednesday-
> evening court-availability monitor. It is not general guidance for the repo.
> If you're here for anything else (dashboard, other venues, refactors, a
> different session), these notes don't apply — don't treat the schedule,
> alert rule, or venue list as constraints on unrelated work.

Target behavior for this routine is to alert when a tennis slot starting
≥19:00 on **Wednesday** flips from booked to free (alert only — no booking).
This is now implemented: `tennis_app/transform.wednesday_evening_openings()`
is the alert rule `pipeline.run()` uses; a generic "any row changed" diff
(`diff_tables`) still exists in `transform.py` but is no longer what triggers
the email.

## What the routine does

- Poller: `.github/workflows/poller.yml`, cron `* * * * *` (every minute).
- Each run: fetch → `tennis_app/pipeline.run()` → email via Gmail SMTP if a Wednesday-evening (>=19:00) slot flipped from booked to free, else log quietly and exit.
- Alerting uses `wednesday_evening_openings()`: a row must be a Wednesday, start at or after 19:00, have `Spaces > 0` now, and have had `Spaces <= 0` (or be unseen) in the previous cached run.
- Cross-run cache: `actions/cache` (keyed per run_id + prefix restore) holds `cache/state.json`. If it's ever lost, the next run has no baseline and correctly stays silent. The cached rows carry a `Time24` column (24h start time) alongside the display `Time` (12h); older cache files without it load fine — the column is just absent until the next full write.
- Secrets the routine needs: `EMAIL_FROM`, `EMAIL_TO`, `APP_PASSWORD` (GH Actions secrets).

## Venues watched

- `islington-tennis-centre` / `tennis-court-indoor` + `tennis-court-outdoor`.
- Highbury Fields is `islington-tennis-centre` / `highbury-tennis` (confirmed via a third-party aggregator's live `booking_url` field, not `islington-parks` as previously guessed). Now in `tennis_app/config.py`.

## Gotchas when working on this routine

- **This sandbox can't reach the booking API** — the agent proxy 403s `better-admin.org.uk` / `bookings.better.org.uk` (WebFetch 403s everything). "API down" is almost always the sandbox, not the API.
- **To test the live fetch, run it on GitHub Actions** (runners have real internet): push a throwaway probe workflow triggered by `push` to the branch (not `workflow_dispatch` — needs the file on default branch), then read the job logs (GitHub Actions UI, `gh run view --log`, or whatever GitHub "get job logs" MCP tool your session exposes — return full content, not just the URL), then delete the probe.
- **Better Admin rate-limits bursts**: ~30 rapid requests → spurious 422s even on known-good combos. Space ~1.5s; keep a known-good control to tell throttling from a bad slug.
- Verify locally without emailing: `PYTHONPATH=. python -m tennis_app --fixtures testing/fixtures/enriched_records.json --cache /tmp/state.json --no-notify` (run twice to exercise the diff path).
