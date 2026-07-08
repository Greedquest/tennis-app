#!/usr/bin/env python3
"""Local Wednesday-evening court watch.

Standalone, cron-friendly script (not the cloud GitHub Actions poller). Run it
every 5 minutes via cron/Termux; it self-guards to only do real work on
Wednesdays between midday and 22:00, so a year-round 5-minute cron entry is
safe to install once. On each in-window run it fetches Wednesday's slots for
the watched venues, keeps only slots starting at or after 19:00, and fires a
desktop notification the moment one flips from fully booked (spaces == 0) to
free (spaces > 0) since the previous check. Alert only -- no booking.

Data source: the Better Admin API (the same one tennis_app/fetch.py uses).
localtenniscourts.com was evaluated as an alternative source but its own
server-side data fetch failed consistently across repeated attempts from a
real network (see git history for the probe); it also has no stable public
JSON API of its own to call (it's a TanStack Start app whose data loads via
an internal, build-hashed server function, not a plain REST/JSON endpoint).

Usage:
    PYTHONPATH=. python scripts/local_court_watch.py
    PYTHONPATH=. python scripts/local_court_watch.py --force --fixtures testing/fixtures/late_wed_slot_booked.json --date 2026-07-08 --cache /tmp/watch.json
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime

from tennis_app.fetch import fetch_activities

# venue/court pairs to watch (Better Admin slugs).
# "islington-parks:highbury-fields-activities" returns HTTP 200 (a real slug)
# but showed 0 records across the next 3 days when this was probed -- confirm
# it's actually carrying slot data before relying on it, e.g.:
#   python scripts/probe_venue.py islington-parks:highbury-fields-activities --days 14
VENUES = [
    ("islington-tennis-centre", "tennis-court-outdoor"),
    ("islington-parks", "highbury-fields-activities"),
]

MIN_START_MINUTES = 19 * 60  # only alert on slots starting >= 19:00
WINDOW_START_MINUTES = 12 * 60  # midday
WINDOW_END_MINUTES = 22 * 60  # 22:00

DEFAULT_CACHE_PATH = os.path.expanduser("~/.cache/tennis-watch/state.json")


def _minutes(hhmm: str) -> int:
    hours, mins = hhmm.split(":")
    return int(hours) * 60 + int(mins)


def in_watch_window(now: datetime) -> bool:
    """Wednesday (weekday() == 2), between midday and 22:00."""
    minutes_of_day = now.hour * 60 + now.minute
    return now.weekday() == 2 and WINDOW_START_MINUTES <= minutes_of_day <= WINDOW_END_MINUTES


def load_cache(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_cache(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def notify(title: str, message: str) -> None:
    """Best-effort desktop notification: Termux, then macOS, then Linux, then print."""
    if shutil.which("termux-notification"):
        subprocess.run(["termux-notification", "--title", title, "--content", message], check=False)
        return
    if sys.platform == "darwin":
        safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
        safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(
            ["osascript", "-e", f'display notification "{safe_message}" with title "{safe_title}"'],
            check=False,
        )
        return
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False)
        return
    logging.warning(
        "No desktop notification backend found (Termux/macOS/notify-send); printing instead."
    )
    print(f"{title}: {message}")


def fetch_raw_records(date: str) -> list[dict]:
    all_records: list[dict] = []
    for venue, court in VENUES:
        try:
            all_records.extend(fetch_activities(venue, court, date))
        except Exception as e:
            logging.warning("Failed to fetch %s/%s for %s: %s", venue, court, date, e)
    return all_records


def filter_late_slots(raw_records: list[dict], date: str) -> list[dict]:
    slots = []
    for activity in raw_records:
        if activity.get("date") != date:
            continue
        time_24h = (activity.get("starts_at") or {}).get("format_24_hour")
        if not time_24h or _minutes(time_24h) < MIN_START_MINUTES:
            continue
        venue = activity.get("venue")
        court = activity.get("court")
        slots.append(
            {
                "key": f"{venue}|{court}|{date}|{time_24h}",
                "venue": venue,
                "court": court,
                "time": time_24h,
                "spaces": activity.get("spaces"),
            }
        )
    return slots


def check(
    cache_path: str,
    *,
    force: bool = False,
    fixtures_path: str | None = None,
    date: str | None = None,
) -> int:
    now = datetime.now()
    if not force and not in_watch_window(now):
        logging.info(
            "Outside the Wednesday watch window (now=%s); skipping.",
            now.isoformat(timespec="minutes"),
        )
        return 0

    target_date = date or now.strftime("%Y-%m-%d")
    logging.info("Checking slots >= 19:00 on %s...", target_date)

    if fixtures_path:
        with open(fixtures_path, encoding="utf-8") as f:
            data = json.load(f)
        raw_records = data["data"] if isinstance(data, dict) and "data" in data else data
    else:
        raw_records = fetch_raw_records(target_date)

    slots = filter_late_slots(raw_records, target_date)

    prev = load_cache(cache_path)
    curr = {}
    opened = []
    for slot in slots:
        curr[slot["key"]] = slot["spaces"]
        prev_spaces = prev.get(slot["key"])
        if prev_spaces == 0 and slot["spaces"] and slot["spaces"] > 0:
            opened.append(slot)

    if opened:
        lines = [f"{s['time']} {s['venue']}/{s['court']} ({s['spaces']} space(s))" for s in opened]
        message = "Just opened up:\n" + "\n".join(lines)
        logging.info(message)
        notify("Tennis court available!", message)
    else:
        logging.info("No newly-opened slots (%d slot(s) checked).", len(slots))

    save_cache(cache_path, curr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local Wednesday-evening court watch (alert only, no booking)."
    )
    parser.add_argument(
        "--cache",
        default=DEFAULT_CACHE_PATH,
        help=f"Path to the cache file (default: {DEFAULT_CACHE_PATH})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run the check even outside the Wednesday noon-22:00 window (for testing).",
    )
    parser.add_argument(
        "--fixtures",
        default=None,
        help="Load raw activity records from a JSON fixture instead of the live API.",
    )
    parser.add_argument(
        "--date", default=None, help="Override the target date (YYYY-MM-DD); defaults to today."
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return check(args.cache, force=args.force, fixtures_path=args.fixtures, date=args.date)


if __name__ == "__main__":
    sys.exit(main())
