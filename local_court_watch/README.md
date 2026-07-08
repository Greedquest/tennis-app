# Wednesday-evening court watch (local script)

Polls [localtenniscourts.com](https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor)
(Highbury Fields + Islington Tennis Centre - Outdoor) every 5 minutes on
Wednesday afternoons/evenings, and fires a desktop/mobile notification the
moment a slot starting at or after 19:00 flips from booked to free.

Alert only — it never books anything.

## Why this isn't a Claude Code routine

Claude Code cloud routines can't run more often than hourly, and this needs
5-minute resolution during a narrow window. So it's a plain script meant to
run on *your own machine* via cron (or Termux + crontab/Tasker on Android),
not something scheduled in this repo's CI.

## How it works

- `parser.py` fetches the page and picks the day-of-week-agnostic "today"
  column out of the hydration data embedded in the HTML (there's no JSON
  API — `/api/availability` explicitly rejects non-HTML requests).
- `watch.py` filters to hours >= 19:00, diffs against the last run's cached
  state (`cache/court_watch_state.json` by default), and notifies only on a
  booked (0 spaces) -> free (>0 spaces) transition.
- `notify.py` sends the alert via whichever of `termux-notification`,
  `notify-send`, or `osascript` is available on the machine, falling back to
  stdout.
- The script itself only takes real action on Wednesdays between 12:00 and
  22:00 local time — safe to invoke more often from cron; it no-ops outside
  that window.

## Setup

```
pip install requests
```

### Linux / Termux crontab

```cron
*/5 12-21 * * 3 cd /path/to/tennis-app && /usr/bin/python3 -m local_court_watch.watch >> ~/.cache/court_watch.log 2>&1
```

(`12-21` covers the 12:00-22:00 window since cron's range is inclusive;
`* * 3` is Wednesday.)

On Termux specifically, install `termux-api` (and the Termux:API companion
app) so `termux-notification` is available, then add the same line via
`crontab -e` (needs the `cronie` package + `termux-services`, or use Tasker
with a "Run Shell" action on the same schedule if you'd rather not run a
cron daemon in the background).

### Testing without waiting for Wednesday

```
python3 -m local_court_watch.watch --force --no-notify --html-file testing/fixtures/localtenniscourts_sample.html --cache /tmp/court_watch_state.json
```

Run it twice with a live fetch (`--force` only, no `--html-file`) to see the
diff path exercised — the first run establishes a baseline silently, and any
run after a slot opens up should notify.
