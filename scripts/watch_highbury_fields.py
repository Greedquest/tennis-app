#!/usr/bin/env python3
"""Local Wednesday-evening watch for Highbury Fields / Islington Tennis Centre (outdoor).

Polls https://localtenniscourts.com for today's availability and fires a
desktop notification the moment a slot starting at or after 19:00 flips
from booked to free. Alert only - no booking automation.

This is a LOCAL script, not a Claude Code routine: routines only run
hourly at best, and this needs 5-minute granularity on Wednesday
afternoons/evenings. Schedule it with cron or Tasker; it exits immediately
outside its target window unless --force is passed.

Data source: the site server-renders the whole availability table (dates,
time rows, per-court counts) into the initial HTML response keyed off the
`?q=` query param - there is no separate JSON API to call. Confirmed by
fetching the page with plain `requests` (no JS execution): the table cells
are already literal <td> markup in that response. A Playwright network
trace of the live page independently confirmed zero XHR/fetch calls fire
for the data - it is genuinely server-rendered, not client-fetched.

The two venues only return data when queried together as one combined
`?q=` value (querying "islington-tennis-centre-outdoor" alone returns an
empty table), so this polls the single combined URL and reports one
merged court count rather than a per-venue breakdown.

Cron (Wednesdays, every 5 min from noon-22:00; the script itself re-checks
the window too, so a simpler `*/5 * * * 3` entry is also safe):
    */5 12-21 * * 3 /usr/bin/python3 /path/to/watch_highbury_fields.py

Termux + Tasker: trigger a profile on "Day of Week = Wed" with a 5-min
repeating interval task that runs the same command; this script calls
`termux-notification` automatically when it's on PATH.

Verify without waiting for Wednesday: --force bypasses the day/time
window; --no-notify logs the alert instead of firing a desktop
notification.
"""

import argparse
import json
import logging
import shutil
import subprocess  # nosec B404 - used only with fixed argv lists below, never shell=True
import sys
from datetime import datetime
from datetime import time as dtime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

VENUE_LABEL = "Highbury Fields / Islington Tennis Centre (Outdoor)"
PAGE_URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

MIN_ALERT_TIME = "19:00"
WINDOW_START = dtime(12, 0)
WINDOW_END = dtime(22, 0)
WEDNESDAY = 2  # datetime.weekday()

DEFAULT_CACHE_PATH = Path.home() / ".cache" / "tennis-watch" / "state.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def fetch_today_slots() -> dict[str, int | None]:
    """Return {time_label: court_count_or_None} for today's column, times >= 19:00 only.

    Today is always the first data column in the table (the site shows a
    rolling window starting from the current day), so we don't need to
    parse the day-header dates at all.
    """
    r = requests.get(PAGE_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    rows = soup.select('tbody[data-slot="table-body"] tr[data-slot="table-row"]')
    slots: dict[str, int | None] = {}
    for row in rows:
        cells = row.select('td[data-slot="table-cell"]')
        if len(cells) < 2:
            continue
        time_label = cells[0].get_text(strip=True)
        if time_label < MIN_ALERT_TIME:
            continue
        span = cells[1].select_one("span.font-semibold")
        text = span.get_text(strip=True) if span else "-"
        slots[time_label] = int(text) if text.isdigit() else None
    return slots


def send_notification(title: str, message: str) -> None:
    if termux_notification := shutil.which("termux-notification"):
        subprocess.run(  # nosec B603 - full resolved path, fixed argv list, no shell
            [termux_notification, "--title", title, "--content", message], check=False
        )
    elif notify_send := shutil.which("notify-send"):
        subprocess.run([notify_send, title, message], check=False)  # nosec B603
    elif osascript := shutil.which("osascript"):
        escaped_message = message.replace("\\", "\\\\").replace('"', '\\"')
        escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
        script = f'display notification "{escaped_message}" with title "{escaped_title}"'
        subprocess.run([osascript, "-e", script], check=False)  # nosec B603
    else:
        log.warning("No desktop notifier found (tried termux-notification/notify-send/osascript).")


def load_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def in_watch_window(now: datetime) -> bool:
    return now.weekday() == WEDNESDAY and WINDOW_START <= now.time() <= WINDOW_END


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE_PATH)
    p.add_argument(
        "--force", action="store_true", help="run even outside the Wed 12:00-22:00 window"
    )
    p.add_argument(
        "--no-notify",
        action="store_true",
        help="log alerts instead of firing a desktop notification",
    )
    args = p.parse_args(argv)

    now = datetime.now()
    if not args.force and not in_watch_window(now):
        log.info("Outside watch window (Wed 12:00-22:00); exiting quietly.")
        return 0

    today_key = now.date().isoformat()
    cache = load_cache(args.cache_path)
    cache = {k: v for k, v in cache.items() if k >= today_key}  # drop stale days
    prev_slots = cache.get(today_key, {})

    try:
        slots = fetch_today_slots()
    except Exception as e:
        log.warning("Failed to fetch availability: %s", e)
        return 1

    for time_label, count in slots.items():
        was_free = prev_slots.get(time_label) is not None
        is_free = count is not None
        if is_free and not was_free:
            courts = f"{count} court{'s' if count != 1 else ''}"
            message = f"{VENUE_LABEL}: {time_label} today just opened up ({courts} free)"
            log.info("ALERT: %s", message)
            if not args.no_notify:
                send_notification("Tennis court free!", message)

    log.info("%s: %s", VENUE_LABEL, slots)

    cache[today_key] = slots
    save_cache(args.cache_path, cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
