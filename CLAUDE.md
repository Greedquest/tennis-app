# Routine: Wednesday-evening court watch

> **Scope:** this file documents ONE recurring task — the scheduled Wednesday-
> evening court-availability monitor. It is not general guidance for the repo.
> If you're here for anything else (dashboard, other venues, refactors, a
> different session), these notes don't apply — don't treat the schedule,
> alert rule, or venue list as constraints on unrelated work.

Target behavior for this routine is to alert when a tennis slot starting
≥19:00 on **Wednesday** flips from booked to free (alert only — no booking).
Current repository code is still on the generic poller/diff flow described
below unless and until the Wednesday-watch implementation lands.

## What the routine does

- Poller (current): `.github/workflows/poller.yml`, cron `* * * * *` (every minute).
- Each run: fetch → `tennis_app/pipeline.run()` → email via Gmail SMTP if a watched slot opened up, else log quietly and exit.
- Alerting (current) uses generic change detection (`diff_tables`) and emails on any detected row change.
- Cross-run cache: `actions/cache` (keyed per run_id + prefix restore) holds `cache/state.json`. If it's ever lost, the next run has no baseline and correctly stays silent.
- Secrets the routine needs: `EMAIL_FROM`, `EMAIL_TO`, `APP_PASSWORD` (GH Actions secrets).

## Venues watched

- `islington-tennis-centre` / `tennis-court-indoor` + `tennis-court-outdoor`.
- Highbury Fields is a probed candidate only, not yet in `tennis_app/config.py`. Best-guess
  slug is `islington-tennis-centre` / `highbury-tennis` (from localtenniscourts.com's
  booking links back to Better Admin — see `scripts/probe_venue.py`), not the earlier
  `islington-parks` / `tennis-court-outdoor` guess. Unconfirmed by a live probe from this
  repo: Better Admin returned 422 on every candidate including the known-good control on
  the last attempt, which reads as rate-limiting rather than a bad slug.

## Gotchas when working on this routine

- **This sandbox can't reach the booking API** — the agent proxy 403s `better-admin.org.uk` / `bookings.better.org.uk` (WebFetch 403s everything). "API down" is almost always the sandbox, not the API.
- **To test the live fetch, run it on GitHub Actions** (runners have real internet): push a throwaway probe workflow triggered by `push` to the branch (not `workflow_dispatch` — needs the file on default branch), then read the job logs (GitHub Actions UI, `gh run view --log`, or whatever GitHub "get job logs" MCP tool your session exposes — return full content, not just the URL), then delete the probe.
- **Better Admin rate-limits bursts**: ~30 rapid requests → spurious 422s even on known-good combos. Space ~1.5s; keep a known-good control to tell throttling from a bad slug.
- Verify locally without emailing: `PYTHONPATH=. python -m tennis_app --fixtures testing/fixtures/enriched_records.json --cache /tmp/state.json --no-notify` (run twice to exercise the diff path).
