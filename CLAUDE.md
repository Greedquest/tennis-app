# Routine: Wednesday-evening court watch

> **Scope:** this file documents ONE recurring task — the scheduled Wednesday-
> evening court-availability monitor. It is not general guidance for the repo.
> If you're here for anything else (dashboard, other venues, refactors, a
> different session), these notes don't apply — don't treat the schedule,
> alert rule, or venue list as constraints on unrelated work.

Target behavior for this routine is to alert when a tennis slot starting
≥19:00 on **Wednesday** flips from booked to free (alert only — no booking).
This has landed: `tennis_app/transform.wednesday_evening_openings()` is the
alert rule and `pipeline.run()` calls it instead of the old generic diff.

## What the routine does

- Poller (current): `.github/workflows/poller.yml`, cron `* * * * *` (every minute, every day — see below for why it isn't Wednesday-only).
- Each run: fetch → `tennis_app/pipeline.run()` → email via Gmail SMTP if a Wed ≥19:00 slot flipped booked→free, else log quietly and exit.
- Alerting rule: `wednesday_evening_openings()` in `transform.py`. A slot only counts if it was observed booked (Spaces <= 0) on the *previous* poll and is free (Spaces > 0) now — no prior observation means no alert, by design.
- Deliberately still polls every day of the week, not just Wednesdays: `fetch_all_activities` looks `days_ahead` (5) days out, so a slot for next Wednesday can open on, say, the preceding Saturday when someone cancels. Restricting the cron to Wednesday-only (as a naive read of "Wednesday watch" might suggest) would miss those early cancellations.
- Cross-run cache: `actions/cache` (keyed per run_id + prefix restore) holds `cache/state.json`. If it's ever lost, the next run has no baseline and correctly stays silent.
- Secrets the routine needs: `EMAIL_FROM`, `EMAIL_TO`, `APP_PASSWORD` (GH Actions secrets).

## Venues watched

- `islington-tennis-centre` / `tennis-court-indoor` + `tennis-court-outdoor`.
- Highbury Fields (`islington-parks` / `tennis-court-outdoor` or `islington-parks` / `highbury-fields-activities`) is still an unconfirmed candidate, not in `tennis_app/config.py`. A GH Actions probe on 2026-07-09 was inconclusive: the known-good control (`islington-tennis-centre:tennis-court-outdoor`) came back 422 (rate-limited — likely from this very poller hammering it every minute), so the Highbury Fields "200 n=0" results can't be trusted as slug confirmation. Re-probe with a control venue the live poller doesn't already hit constantly, or on a day the poller is paused.

## Gotchas when working on this routine

- **This sandbox can't reach the booking API** — the agent proxy 403s `better-admin.org.uk` / `bookings.better.org.uk` (WebFetch 403s everything). "API down" is almost always the sandbox, not the API.
- **To test the live fetch, run it on GitHub Actions** (runners have real internet): push a throwaway probe workflow triggered by `push` to the branch (not `workflow_dispatch` — needs the file on default branch), then read the job logs (GitHub Actions UI, `gh run view --log`, or whatever GitHub "get job logs" MCP tool your session exposes — return full content, not just the URL), then delete the probe.
- **Better Admin rate-limits bursts**: ~30 rapid requests → spurious 422s even on known-good combos. Space ~1.5s; keep a known-good control to tell throttling from a bad slug.
- Verify locally without emailing: `PYTHONPATH=. python -m tennis_app --fixtures testing/fixtures/enriched_records.json --cache /tmp/state.json --no-notify` (run twice to exercise the diff path).
- `localtenniscourts.com` (a third-party aggregator covering Highbury Fields + Islington Tennis Centre) was investigated as a possible alternative data source on 2026-07-09. It's reachable from GH Actions (not from this sandbox — same proxy block as above) but is a client-rendered SPA that caches data in `sessionStorage`; a plain `curl` of the HTML shows no inline API endpoint, so pinning down its real data source would need a real browser network trace, not just curl. Given the existing Better Admin API path already works for these venues, that's the one to build on rather than reverse-engineering this site.
