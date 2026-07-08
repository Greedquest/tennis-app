#!/usr/bin/env python3
"""Local Wednesday-evening court watch: alert the moment a >=19:00 Wednesday
slot flips from booked to free. Alert only - no booking automation.

This is a standalone local script, not a Claude Code routine (routines are
hourly-minimum, too coarse for a 5-minute Wednesday-evening check). Schedule
it yourself with cron or Tasker/Termux:API, e.g. a crontab entry that covers
Wednesday midday through 22:00:

    */5 12-21 * * 3 cd /path/to/tennis-app && PYTHONPATH=. python3 scripts/wednesday_evening_watch.py
    0    22   * * 3 cd /path/to/tennis-app && PYTHONPATH=. python3 scripts/wednesday_evening_watch.py

The script also re-checks the day/time window itself before fetching
anything, so a slightly loose cron (or a Tasker task firing every 5 minutes
all week) is safe - it just logs quietly and exits outside the window.

Verify without hitting the live API or sending a notification:
    PYTHONPATH=. python3 scripts/wednesday_evening_watch.py \\
        --fixtures testing/fixtures/enriched_records.json \\
        --cache /tmp/wednesday_watch_state.json --force --no-notify
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tennis_app.fetch import fetch_activities  # noqa: E402

# Highbury Fields slug is a best guess (see scripts/probe_venue.py); Islington
# Tennis Centre outdoor is already confirmed via tennis_app/config.py.
VENUES = [
    {"venue": "islington-tennis-centre", "court": "tennis-court-outdoor"},
    {"venue": "islington-tennis-centre", "court": "highbury-tennis"},
]

MIN_START_HOUR = 19  # only alert for slots starting at or after 19:00
WATCH_WEEKDAY = 2  # Monday=0 ... Wednesday=2
WINDOW_START_HOUR = 12
WINDOW_END_HOUR = 22

DEFAULT_CACHE_PATH = os.getenv("WEDNESDAY_WATCH_CACHE", "cache/wednesday_watch_state.json")


def in_watch_window(now: datetime) -> bool:
    """Wednesday, midday through 22:00 local time."""
    return now.weekday() == WATCH_WEEKDAY and WINDOW_START_HOUR <= now.hour < WINDOW_END_HOUR


def _slot_hour(activity: dict[str, Any]) -> int | None:
    hour_str = (activity.get("starts_at") or {}).get("format_24_hour", "")
    try:
        return int(hour_str.split(":")[0])
    except (ValueError, IndexError):
        return None


def fetch_evening_slots(target_date: str) -> list[dict[str, Any]]:
    """Fetch live activities for each watched venue/court and keep >=19:00 starts."""
    slots = []
    for vc in VENUES:
        try:
            activities = fetch_activities(vc["venue"], vc["court"], target_date)
        except Exception as e:
            logging.warning("Fetch failed for %s/%s: %s", vc["venue"], vc["court"], e)
            continue
        for activity in activities:
            hour = _slot_hour(activity)
            if hour is not None and hour >= MIN_START_HOUR:
                slots.append(
                    {
                        "venue": vc["venue"],
                        "court": vc["court"],
                        "date": target_date,
                        "time": activity["starts_at"]["format_24_hour"],
                        "spaces": activity.get("spaces"),
                    }
                )
    return slots


def evening_slots_from_fixture(path: str) -> list[dict[str, Any]]:
    """Same >=19:00 filtering, but from a fixture file instead of the live API."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    records = data["data"] if isinstance(data, dict) and "data" in data else data

    slots = []
    for activity in records:
        hour = _slot_hour(activity)
        if hour is not None and hour >= MIN_START_HOUR:
            slots.append(
                {
                    "venue": activity.get("venue"),
                    "court": activity.get("court"),
                    "date": activity.get("date"),
                    "time": activity["starts_at"]["format_24_hour"],
                    "spaces": activity.get("spaces"),
                }
            )
    return slots


def slot_key(slot: dict[str, Any]) -> str:
    return f"{slot['date']}|{slot['time']}|{slot['venue']}|{slot['court']}"


def load_cache(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(path: str, state: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def find_freed_slots(prev_state: dict[str, Any], curr_state: dict[str, Any]) -> list[str]:
    """Keys where spaces went from 0 (booked out) to >0 (free) - alert only on that transition."""
    freed = []
    for key, curr_spaces in curr_state.items():
        prev_spaces = prev_state.get(key)
        if prev_spaces == 0 and curr_spaces:
            freed.append(key)
    return freed


def notify(title: str, message: str) -> None:
    """Best-effort desktop notification: Termux, then Linux, then macOS, then a log line."""
    if shutil.which("termux-notification"):
        subprocess.run(["termux-notification", "--title", title, "--content", message], check=False)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False)
    elif shutil.which("osascript"):
        safe_message = message.replace('"', "'")
        safe_title = title.replace('"', "'")
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        subprocess.run(["osascript", "-e", script], check=False)
    else:
        logging.warning("NOTIFY (no notification backend found): %s - %s", title, message)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--cache",
        default=DEFAULT_CACHE_PATH,
        help=f"Cache file path (default: {DEFAULT_CACHE_PATH})",
    )
    p.add_argument(
        "--fixtures", help="JSON fixture file of activity records, instead of the live API"
    )
    p.add_argument(
        "--force", action="store_true", help="Run even outside the Wed 12:00-22:00 window"
    )
    p.add_argument(
        "--no-notify", action="store_true", help="Disable the desktop notification (for testing)"
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    now = datetime.now()
    if not args.force and not in_watch_window(now):
        logging.info("Outside the Wednesday 12:00-22:00 watch window; skipping.")
        return 0

    if args.fixtures:
        logging.info("Loading evening slots from fixture file: %s", args.fixtures)
        slots = evening_slots_from_fixture(args.fixtures)
    else:
        target_date = now.date().isoformat()
        logging.info("Fetching >=19:00 slots for %s...", target_date)
        slots = fetch_evening_slots(target_date)

    prev_state = load_cache(args.cache)
    curr_state = {slot_key(s): s.get("spaces") for s in slots}

    freed = find_freed_slots(prev_state, curr_state)
    logging.info("Checked %d Wednesday-evening slot(s); %d freed up.", len(slots), len(freed))

    if freed:
        lines = [f"{k.split('|')[1]} - {k.split('|')[3]}" for k in freed]
        message = "; ".join(lines)
        logging.info("Slot(s) freed up: %s", message)
        if not args.no_notify:
            notify("Tennis court freed up!", message)

    save_cache(args.cache, curr_state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
