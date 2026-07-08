# Routine: Wednesday-evening court watch

> **Scope:** this file documents ONE recurring task — the scheduled Wednesday-
> evening court-availability monitor. It is not general guidance for the repo.
> If you're here for anything else (dashboard, other venues, refactors, a
> different session), these notes don't apply — don't treat the schedule,
> alert rule, or venue list as constraints on unrelated work.

Target behavior for this routine is to alert when a tennis slot starting
≥19:00 on **Wednesday** flips from booked to free (alert only — no booking).
This is now the live implementation (landed via `filter_wednesday_evening` +
`diff_booked_to_free` in `tennis_app/transform.py`, wired through
`tennis_app/pipeline.run()`).

## What the routine does

- Poller: `.github/workflows/poller.yml`, cron `* * * * *` (every minute).
- Each run: fetch (7 days ahead, so the upcoming Wednesday is always in range) → `tennis_app/pipeline.run()` → email via Gmail SMTP if a watched slot flipped from booked to free, else log quietly and exit.
- Alerting filters raw records to Wednesday slots starting ≥19:00 (`filter_wednesday_evening`), then emails only on a 0-spaces→>0-spaces flip (`diff_booked_to_free`). Non-Wednesday and daytime slots never reach the diff, so they can't trigger an email.
- Cross-run cache: `actions/cache` (keyed per run_id + prefix restore) holds `cache/state.json` — now scoped to Wednesday-evening rows only. If it's ever lost, the next run has no baseline and correctly stays silent.
- Secrets the routine needs: `EMAIL_FROM`, `EMAIL_TO`, `APP_PASSWORD` (GH Actions secrets).

## Venues watched

- `islington-tennis-centre` / `tennis-court-indoor` + `tennis-court-outdoor`.
- Highbury Fields (`islington-parks` / `tennis-court-outdoor`) is now active in `tennis_app/config.py`.
- `localtenniscourts.com` (a third-party aggregator UI) was evaluated as a possible data source and rejected: it's a client-rendered Next.js app with no JSON API, and its own server-side data fetch was erroring out ("Oops! There was a problem loading the court availability data") when probed from GitHub Actions. Better Admin remains the direct, reliable source.

## Gotchas when working on this routine

- **This sandbox can't reach the booking API** — the agent proxy 403s `better-admin.org.uk` / `bookings.better.org.uk` (WebFetch 403s everything). "API down" is almost always the sandbox, not the API.
- **To test the live fetch, run it on GitHub Actions** (runners have real internet): push a throwaway probe workflow triggered by `push` to the branch (not `workflow_dispatch` — needs the file on default branch), then read the job logs (GitHub Actions UI, `gh run view --log`, or whatever GitHub "get job logs" MCP tool your session exposes — return full content, not just the URL), then delete the probe.
- **Better Admin rate-limits bursts**: ~30 rapid requests → spurious 422s even on known-good combos. Space ~1.5s; keep a known-good control to tell throttling from a bad slug.
- Verify locally without emailing: `PYTHONPATH=. python -m tennis_app --fixtures testing/fixtures/enriched_records.json --cache /tmp/state.json --no-notify` (run twice to exercise the diff path).
