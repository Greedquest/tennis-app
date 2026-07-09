#!/usr/bin/env python3
"""Local watcher: alert when a Wednesday-evening (>=19:00) slot opens up.

This is NOT meant to run as a cloud routine -- Claude Code routines fire at
most hourly, and this needs a 5-minute cadence for a few hours one day a
week. Run it yourself via cron / Termux's crond / Tasker:

    */5 12-21 * * 3 cd /path/to/tennis-app && python scripts/watch_wednesday_evening.py

(the script also no-ops outside Wednesday noon-22:00 so an accidental
broader cron schedule won't spam requests or notifications).

Desktop notification only -- no booking automation. Mr Hall books manually.
"""

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tennis_app.config import VENUES  # noqa: E402
from tennis_app.fetch import fetch_all_activities  # noqa: E402

WEDNESDAY = 2  # datetime.weekday(): Monday=0 ... Sunday=6
WINDOW_START_HOUR = 12
WINDOW_END_HOUR = 22
EVENING_CUTOFF = "19:00"  # zero-padded 24h, so string comparison is safe

DEFAULT_CACHE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "cache", "wednesday_evening_state.json"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def in_watch_window(now: datetime) -> bool:
    return now.weekday() == WEDNESDAY and WINDOW_START_HOUR <= now.hour < WINDOW_END_HOUR


def key_of(rec: dict) -> str:
    return f"{rec['date']}|{rec['time_24h']}|{rec['venue']}|{rec['court']}"


def filter_wednesday_evening(raw_records: list[dict]) -> dict[str, dict]:
    """Keep only Wednesday slots starting >=19:00, keyed for diffing."""
    out: dict[str, dict] = {}
    for rec in raw_records:
        date_str = rec.get("date")
        starts_at = rec.get("starts_at") or {}
        time_24h = starts_at.get("format_24_hour")
        if not date_str or not time_24h:
            continue
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if day.weekday() != WEDNESDAY or time_24h < EVENING_CUTOFF:
            continue

        flat = {
            "date": date_str,
            "time_24h": time_24h,
            "time_12h": starts_at.get("format_12_hour"),
            "venue": rec.get("venue"),
            "court": rec.get("court"),
            "spaces": rec.get("spaces"),
        }
        out[key_of(flat)] = flat
    return out


def load_prev(cache_path: str) -> dict[str, dict]:
    try:
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_curr(cache_path: str, curr: dict[str, dict]) -> None:
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    tmp = cache_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(curr, f, indent=2)
    os.replace(tmp, cache_path)


def find_newly_free(prev: dict[str, dict], curr: dict[str, dict]) -> list[dict]:
    """Slots that were booked (spaces 0, or unseen) and are now free (spaces > 0)."""
    newly_free = []
    for key, rec in curr.items():
        spaces = rec.get("spaces") or 0
        if spaces <= 0:
            continue
        prev_rec = prev.get(key)
        prev_spaces = (prev_rec or {}).get("spaces") or 0
        if prev_spaces <= 0:
            newly_free.append(rec)
    return newly_free


def notify_desktop(title: str, message: str) -> None:
    system = platform.system()
    try:
        if shutil.which("termux-notification"):
            subprocess.run(
                ["termux-notification", "--title", title, "--content", message],
                check=False,
            )
        elif system == "Linux" and shutil.which("notify-send"):
            subprocess.run(["notify-send", title, message], check=False)
        elif system == "Darwin":
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], check=False)
        elif system == "Windows":
            from plyer import notification  # type: ignore[import-not-found]

            notification.notify(title=title, message=message, timeout=30)
        else:
            logging.warning("No notification backend found; printing instead.")
            print(f"{title}: {message}")
    except Exception:
        logging.exception("Failed to send desktop notification; printing instead.")
        print(f"{title}: {message}")


def main(argv: list[str] | None = None) -> int:
    now = datetime.now()
    force = argv is not None and "--force" in argv
    if not force and not in_watch_window(now):
        logging.info("Outside the Wednesday 12:00-22:00 watch window; exiting quietly.")
        return 0

    cache_path = DEFAULT_CACHE_PATH
    for arg in argv or []:
        if arg.startswith("--cache="):
            cache_path = arg.split("=", 1)[1]

    logging.info("Fetching activities…")
    raw_records = fetch_all_activities(venues=VENUES, days_ahead=8)

    curr = filter_wednesday_evening(raw_records)
    prev = load_prev(cache_path)

    newly_free = find_newly_free(prev, curr)
    if newly_free:
        lines = [
            f"{r['date']} {r['time_12h']} — {r['venue']}/{r['court']} ({r['spaces']} space(s))"
            for r in newly_free
        ]
        message = "\n".join(lines)
        logging.info("Newly available Wednesday-evening slot(s):\n%s", message)
        notify_desktop("Tennis court free!", message)
    else:
        logging.info("Checked %d Wednesday-evening slot(s); no change.", len(curr))

    save_curr(cache_path, curr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
