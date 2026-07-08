# Routine: Wednesday-evening court watch

> **Scope:** this file documents ONE recurring task — the scheduled Wednesday-
> evening court-availability monitor. It is not general guidance for the repo.
> If you're here for anything else (dashboard, other venues, refactors, a
> different session), these notes don't apply — don't treat the schedule,
> alert rule, or venue list as constraints on unrelated work.

Target behavior for this routine is to alert when a tennis slot starting
≥19:00 on **Wednesday** flips from booked to free (alert only — no booking).
This is now implemented: `tennis_app/transform.py::opened_up_keys` restricts
to watched slots (`is_watched_slot`: Wednesday + `Time24 >= "19:00"`) and only
fires when a slot's `Spaces` goes from `0` to `>0` versus the cached baseline.

## What the routine does

- Poller: `.github/workflows/poller.yml`, cron `*/5 11-21 * * 3` + `0 22 * * 3`
  (every 5 min, Wednesdays only, UK midday-22:00 local — window widened by an
  hour in UTC terms to cover both GMT and BST without a DST-aware schedule).
- Each run: fetch → `tennis_app/pipeline.run()` → email via Gmail SMTP if a watched slot opened up, else log quietly and exit.
- Alerting compares only watched (Wednesday ≥19:00) slots and fires only on a booked→free flip (`opened_up_keys`), not on any row change. A generic `diff_tables` count is still logged for visibility but never triggers an email on its own.
- Cross-run cache: `actions/cache` (keyed per run_id + prefix restore) holds `cache/state.json`. If it's ever lost, the next run has no baseline and correctly stays silent (no prior row to flip *from*).
- Secrets the routine needs: `EMAIL_FROM`, `EMAIL_TO`, `APP_PASSWORD` (GH Actions secrets).

## Venues watched

- `islington-tennis-centre` / `tennis-court-indoor` + `tennis-court-outdoor`.
- Highbury Fields is **not** in `tennis_app/config.py` yet — still unresolved after two probe rounds:
  - Better Admin slug `islington-parks`/`tennis-court-outdoor` and the untried
    `islington-parks`/`highbury-fields-activities`: both structurally valid
    (HTTP 200) but return **0 records** on every probed date. `highbury-fields`/
    `tennis-court-outdoor` and `islington-parks`/`highbury-fields` both 404. The
    known-good control (`islington-tennis-centre`/`tennis-court-outdoor`) got
    rate-limited (422) on the same probe run, so the 404s aren't fully trustworthy
    yet — re-run with the control isolated/spaced out before treating them as final.
  - `localtenniscourts.com` (the site named in the original brief as a
    Highbury+ITC-outdoor aggregator) is a client-rendered SPA (Vite bundle,
    no `__NEXT_DATA__`/`__INITIAL_STATE__`) — a plain `curl` of the page returns
    no embedded JSON and no discoverable API URL. Its data comes from
    client-side JS calls; the actual endpoint is inside `/assets/*.js`, which a
    static fetch doesn't reveal. Next step if pursuing this venue: fetch and
    grep the JS bundle for the API base URL, or drive it with a headless
    browser (e.g. Playwright) and capture the network requests it makes.
  - Until one of these resolves to a real, non-empty feed, don't add Highbury
    to `VENUES` — a 0-record "valid" slug would silently never alert while
    looking configured.

## Gotchas when working on this routine

- **This sandbox can't reach the booking API** — the agent proxy 403s `better-admin.org.uk` / `bookings.better.org.uk` (WebFetch 403s everything). "API down" is almost always the sandbox, not the API.
- **To test the live fetch, run it on GitHub Actions** (runners have real internet): push a throwaway probe workflow triggered by `push` to the branch (not `workflow_dispatch` — needs the file on default branch), then read the job logs (GitHub Actions UI, `gh run view --log`, or whatever GitHub "get job logs" MCP tool your session exposes — return full content, not just the URL), then delete the probe.
- **Better Admin rate-limits bursts**: ~30 rapid requests → spurious 422s even on known-good combos. Space ~1.5s; keep a known-good control to tell throttling from a bad slug.
- Verify locally without emailing: `PYTHONPATH=. python -m tennis_app --fixtures testing/fixtures/enriched_records.json --cache /tmp/state.json --no-notify` (run twice to exercise the diff path). For the watched-slot alert specifically, use `testing/fixtures/wednesday_evening_before.json` then `..._after.json` against the same `--cache` path — the after fixture flips a Wednesday-19:00 slot from `spaces: 0` to `spaces: 2`; a Wednesday-18:00 and a Thursday-19:00 control row flip the same way but must NOT alert.
