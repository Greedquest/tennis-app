# Local Wednesday-evening court watch (experimental)

Alerts the moment a slot starting **>=19:00 on Wednesday** flips from booked to free, on
`https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor`
(Highbury Fields + Islington Tennis Centre outdoor). Alert only -- booking is still manual.

This is **not** the cloud poller documented in `CLAUDE.md` / `.github/workflows/poller.yml`.
That pipeline hits `better-admin.org.uk` every minute via GitHub Actions and emails on any
change. This is a separate, local script requested for a tighter Wednesday-only alert,
because Claude Code cloud routines are hourly-minimum and can't do 5-minute Wednesday
polling. It runs on your own machine's cron (or Termux + Tasker on Android), not in CI.

## Status: unverified data source

The dev sandbox this was built in can't reach `localtenniscourts.com` (outbound network is
proxied and blocks it, the same way it blocks `better-admin.org.uk`), so the parsing in
`tennis_app/wednesday_watch.py` has never seen a real response from the site. Before relying
on this:

1. Run `python scripts/probe_localtenniscourts.py` somewhere with real network egress (a
   laptop, a throwaway GitHub Actions push-triggered workflow, etc. -- same trick
   `scripts/probe_venue.py` uses for the better-admin.org.uk poller).
2. Check whether the page embeds a JSON state blob (`__NEXT_DATA__` / `__NUXT__` /
   `__INITIAL_STATE__`) or loads slots via a separate XHR/fetch call (check your browser's
   Network tab) or needs pure HTML scraping.
3. Adjust `_extract_embedded_json` / `_parse_html_fallback` / `normalise_slot` in
   `tennis_app/wednesday_watch.py` to match what you find.

## Manual test

```sh
pip install -r requirements.txt
PYTHONPATH=. python scripts/wednesday_watch.py --force --dry-run
```

`--force` bypasses the Wednesday/midday-22:00 window so you can test on any day;
`--dry-run` logs what it would alert on without firing a notification.

## Scheduling

Cron (Linux/macOS/Termux), every 5 minutes, Wednesdays, midday-22:00 -- the script itself
also re-checks the window, so a stray cron misfire stays silent:

```cron
*/5 12-21 * * 3 cd /path/to/tennis-app && PYTHONPATH=. python3 scripts/wednesday_watch.py >> logs/wednesday_watch.log 2>&1
```

On Termux, install the Termux:API app + `pkg install termux-api` so `termux-notification`
is available; `notify()` in `tennis_app/wednesday_watch.py` falls back to `notify-send` on a
Linux desktop, or a plain printed `[ALERT]` line if neither is present.

## Cache

State lives in `cache/wednesday_state.json` (gitignored, matches the cloud poller's
`cache/state.json` convention) -- delete it to reset the baseline; the next run will then
see everything as "first sighting" and stay quiet until something actually flips.
