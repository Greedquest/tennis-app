#!/usr/bin/env python3
"""Local Wednesday-evening court watcher for localtenniscourts.com.

Standalone script, not part of the ``tennis_app`` GitHub Actions poller.
That pipeline polls ``better-admin.org.uk`` directly, runs in the cloud every
minute, and emails on *any* availability change. This script is a different,
narrower tool: it polls localtenniscourts.com (which itself aggregates
Highbury Fields + Islington Tennis Centre outdoor from the same underlying
booking system) and fires a desktop notification only when a Wednesday
slot starting at or after 19:00 flips from fully booked to free. It's meant
to run locally via cron / Termux, not as a cloud routine — routines run at
most hourly, and this needs 5-minute polling for a few hours a week.

Why scrape HTML instead of calling a JSON API: localtenniscourts.com is a
TanStack Start app that server-renders its data into the initial HTML as a
streamed JS object (assignments to a ``$R[]`` array — TanStack's "seroval"
serialization), not a REST endpoint returning clean JSON. Devtools network
inspection (a Playwright probe run on a GitHub Actions runner, since this
sandbox's proxy 403s the site) showed *zero* client-side XHR/fetch calls for
availability data — everything needed is already embedded in the page's
initial HTML response, keyed by ``tableData.rows[].dayDDMM.spaces[]``. So a
plain HTTP GET + regex extraction is the actual "check network requests
first" answer here, not a fallback.

Data freshness caveat: localtenniscourts.com scrapes the underlying booking
API on its own schedule — observed ``freshness`` values were "~10 mins ago".
A flip can lag up to ~10 minutes behind the real booking system.

Usage:
    python scripts/watch_wednesday_courts.py
    python scripts/watch_wednesday_courts.py --no-notify   # test without alerting
    python scripts/watch_wednesday_courts.py --force       # bypass the Wednesday/time-window guard

Scheduling (see the bottom of this file for cron/Tasker recipes).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Any

import requests

LTC_URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"
DEFAULT_CACHE_PATH = os.path.expanduser("~/.cache/tennis-app/ltc_wednesday_state.json")
MIN_START_HOUR = 19  # only alert on slots starting at or after 19:00
WATCH_WINDOW = range(12, 22)  # midday (12) through 21:xx; script is a no-op outside this

# Regex over the raw HTML for the embedded $R[]-serialized table.
# Column headers: title:"Wed 08",field:"day0807"
_COLUMN_RE = re.compile(r'title:"([^"]+)",field:"(day\d{4})"')
# Row start: hour:8,fromTime:"08:00"
_ROW_RE = re.compile(r'hour:(\d+),fromTime:"(\d{2}:\d{2})"')
# Per-day slot cell within a row: day0807:$R[N]={day:"08 Jul",total_spaces:0,spaces:$R[M]=[...]}
_DAY_CELL_RE = re.compile(
    r'day(\d{4}):\$R\[\d+\]=\{day:"([^"]+)",total_spaces:(\d+),spaces:\$R\[\d+\]=\[(.*?)\]\}'
)
# Per-venue entry inside a day cell's spaces array.
_VENUE_ENTRY_RE = re.compile(
    r'\$R\[\d+\]=\{venue_id:(\d+),name:"([^"]*)",total_spaces:(\d+),'
    r'scraped_at:"([^"]*)",freshness:"([^"]*)",booking_url:"([^"]*)"\}'
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s"
)


def fetch_html(url: str = LTC_URL) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html",
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.text


def parse_wednesday_slots(html: str) -> list[dict[str, Any]]:
    """Extract slots (any hour) for whichever column is titled "Wed …".

    Returns a list of dicts: fromTime, venue_id, venue_name, spaces, booking_url.
    """
    wednesday_field = None
    for title, field in _COLUMN_RE.findall(html):
        if title.startswith("Wed"):
            wednesday_field = field
            break
    if wednesday_field is None:
        logging.warning("No Wednesday column found in page — nothing to check.")
        return []

    slots: list[dict[str, Any]] = []
    rows = list(_ROW_RE.finditer(html))
    for i, row_match in enumerate(rows):
        from_time = row_match.group(2)
        row_start = row_match.end()
        row_end = rows[i + 1].start() if i + 1 < len(rows) else len(html)
        row_text = html[row_start:row_end]

        for field_digits, _day_label, _total, spaces_body in _DAY_CELL_RE.findall(row_text):
            if f"day{field_digits}" != wednesday_field:
                continue
            for (
                venue_id,
                name,
                total_spaces,
                _scraped_at,
                _freshness,
                booking_url,
            ) in _VENUE_ENTRY_RE.findall(spaces_body):
                slots.append(
                    {
                        "fromTime": from_time,
                        "venue_id": venue_id,
                        "venue_name": name,
                        "spaces": int(total_spaces),
                        "booking_url": booking_url,
                    }
                )
    return slots


def filter_evening_slots(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in slots if int(s["fromTime"][:2]) >= MIN_START_HOUR]


def slot_key(slot: dict[str, Any]) -> str:
    return f"{slot['venue_id']}|{slot['fromTime']}"


def load_state(path: str) -> dict[str, dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.info(
            "No cached state at %s; starting fresh (no baseline, staying silent this run).", path
        )
        return {}
    except json.JSONDecodeError:
        logging.warning("Cached state at %s is corrupt; starting fresh.", path)
        return {}


def save_state(path: str, state: dict[str, dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def find_newly_free(
    prev: dict[str, dict[str, Any]], curr: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Slots that had 0 spaces last poll and have >0 spaces now."""
    newly_free = []
    for key, curr_slot in curr.items():
        prev_slot = prev.get(key)
        if prev_slot is not None and prev_slot["spaces"] == 0 and curr_slot["spaces"] > 0:
            newly_free.append(curr_slot)
    return newly_free


def notify(title: str, message: str) -> None:
    """Best-effort desktop notification: Termux, then Linux notify-send, then macOS osascript."""
    if _try_cmd(["termux-notification", "--title", title, "--content", message]):
        return
    if _try_cmd(["notify-send", title, message]):
        return
    script = f'display notification "{message}" with title "{title}"'
    if _try_cmd(["osascript", "-e", script]):
        return
    logging.warning("No notification backend available; printing instead:\n%s: %s", title, message)


def _try_cmd(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Wednesday-evening tennis court watcher (localtenniscourts.com)"
    )
    p.add_argument(
        "--cache",
        default=DEFAULT_CACHE_PATH,
        help=f"State file path (default: {DEFAULT_CACHE_PATH})",
    )
    p.add_argument("--url", default=LTC_URL, help="localtenniscourts.com query URL to poll")
    p.add_argument(
        "--no-notify", action="store_true", help="Skip the desktop notification (for testing)"
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Run even if it's not currently Wednesday 12:00-21:59 local time",
    )
    p.add_argument(
        "--html-file",
        default=None,
        help="Parse a saved HTML file instead of fetching (for testing)",
    )
    args = p.parse_args(argv)

    now = datetime.now()
    if not args.force and not (now.weekday() == 2 and now.hour in WATCH_WINDOW):
        logging.info("Outside the Wednesday 12:00-22:00 watch window; nothing to do.")
        return 0

    if args.html_file:
        with open(args.html_file, encoding="utf-8") as f:
            html = f.read()
    else:
        logging.info("Fetching %s ...", args.url)
        html = fetch_html(args.url)

    slots = filter_evening_slots(parse_wednesday_slots(html))
    if not slots:
        logging.info("No Wednesday >=19:00 slots found on the page.")
        return 0

    curr_state = {slot_key(s): s for s in slots}
    prev_state = load_state(args.cache)
    newly_free = find_newly_free(prev_state, curr_state)

    if newly_free:
        lines = [f"{s['venue_name']} {s['fromTime']} — {s['booking_url']}" for s in newly_free]
        message = "\n".join(lines)
        logging.info("Slot(s) opened up:\n%s", message)
        if not args.no_notify:
            notify("Tennis court free!", message)
    else:
        logging.info("Checked %d evening slot(s); no change.", len(slots))

    save_state(args.cache, curr_state)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# ---------------------------------------------------------------------------
# Scheduling
#
# Linux/macOS cron (every 5 min, Wednesdays, 12:00-21:55):
#   */5 12-21 * * 3 cd /path/to/tennis-app && /usr/bin/python3 scripts/watch_wednesday_courts.py >> ~/.cache/tennis-app/ltc_watch.log 2>&1
#
# Termux (crontab via termux-services, or Tasker "Run Shell" action on the
# same schedule). Desktop notification uses `termux-notification` from the
# termux-api package — install with `pkg install termux-api` and the
# Termux:API companion app.
#
# Note: the script also self-guards on weekday/hour, so an over-eager cron
# schedule (e.g. every 5 min all week) is harmless — it'll just no-op outside
# the window.
# ---------------------------------------------------------------------------
