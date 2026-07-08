#!/usr/bin/env python3
"""Local Wednesday-evening court-availability watch.

Meant to run every 5 minutes, Wednesday only, via cron / Termux:Crond /
Tasker on a machine you control -- NOT as a cloud routine (those run no
more often than hourly, far too coarse for this). Alerts the moment a
slot starting >= 19:00 today flips from booked to free, for:

  - Islington Tennis Centre (outdoor)
  - Highbury Fields

Alert only -- no booking automation; you still book manually.

Data source: the same Better Admin API this project already polls (see
tennis_app/fetch.py), not the localtenniscourts.com aggregator originally
suggested. That site ships no client-side API to call directly -- its
court data is loaded server-side, and every probe attempt (from GitHub
Actions and from this sandbox) got back a generic "problem loading the
court availability data" error instead of real slots. Better Admin is
already proven reachable and is what the rest of this repo depends on.

Setup (cron, spelled out for every-5-minutes on Wednesdays only -- the
script itself also checks the day/window, so a coarser cron is safe too):

    */5 * * * 3 cd /path/to/tennis-app && python3 scripts/wednesday_watch.py >> wednesday_watch.log 2>&1

Termux: same crontab line via `crontab -e` with Termux:Crond installed,
or a Tasker profile that shells out to the same command on Wednesdays.

Verify without waiting for a real Wednesday or without notifying:

    python scripts/wednesday_watch.py --force --dry-run
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import date, datetime
from datetime import time as dt_time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis_app.fetch import fetch_activities  # noqa: E402

# Best-guess Highbury Fields court slugs. Better Admin rate-limited every
# probe made while wiring this up (see CLAUDE.md's "Gotchas" section), so
# neither candidate below was fully confirmed against real slot data --
# both returned HTTP 200 with zero records, which is consistent with
# "valid but nothing free right now" but not proof the slug is right.
# Confirm properly with:
#   python scripts/probe_venue.py islington-parks:highbury-fields-activities islington-parks:tennis-court-outdoor
# Whichever candidate is wrong just returns 0 records every run, so
# leaving both in here is harmless.
VENUES = [
    {"venue": "islington-tennis-centre", "court": "tennis-court-outdoor"},
    {"venue": "islington-parks", "court": "highbury-fields-activities"},
    {"venue": "islington-parks", "court": "tennis-court-outdoor"},
]

MIN_START_TIME = "19:00"
WINDOW_START = dt_time(12, 0)
WINDOW_END = dt_time(22, 0)
WEDNESDAY = 2  # datetime.weekday(): Monday=0 ... Sunday=6

DEFAULT_STATE_FILE = os.getenv("WEDNESDAY_WATCH_STATE", "cache/wednesday_watch_state.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def in_watch_window(now: datetime) -> bool:
    return now.weekday() == WEDNESDAY and WINDOW_START <= now.time() <= WINDOW_END


def slot_key(venue: str, court: str, today: str, starts_at: str) -> str:
    return f"{today}|{starts_at}|{venue}:{court}"


def is_free(rec: dict) -> bool:
    return (rec.get("spaces") or 0) > 0


def load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def notify(title: str, body: str) -> None:
    if shutil.which("termux-notification"):
        subprocess.run(["termux-notification", "--title", title, "--content", body], check=False)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, body], check=False)
    elif sys.platform == "darwin":
        script = f"display notification {body!r} with title {title!r}"
        subprocess.run(["osascript", "-e", script], check=False)
    else:
        logging.warning("No desktop/Termux notifier found; alert was: %s -- %s", title, body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wednesday-evening court-availability watch")
    parser.add_argument("--state-file", default=DEFAULT_STATE_FILE)
    parser.add_argument("--dry-run", action="store_true", help="check for changes but don't notify")
    parser.add_argument(
        "--force", action="store_true", help="ignore the Wednesday/12:00-22:00 window (for testing)"
    )
    args = parser.parse_args(argv)

    now = datetime.now()
    if not args.force and not in_watch_window(now):
        logging.info("Outside the Wednesday 12:00-22:00 watch window; exiting quietly.")
        return 0

    today = date.today().strftime("%Y-%m-%d")
    prev_state = load_state(args.state_file)
    curr_state: dict[str, dict] = {}
    newly_free: list[str] = []

    for vc in VENUES:
        venue, court = vc["venue"], vc["court"]
        try:
            records = fetch_activities(venue, court, today)
        except Exception as e:
            logging.warning("Fetch failed for %s/%s: %s", venue, court, e)
            continue

        for rec in records:
            starts_at = (rec.get("starts_at") or {}).get("format_24_hour")
            if not starts_at or starts_at < MIN_START_TIME:
                continue

            key = slot_key(venue, court, today, starts_at)
            free_now = is_free(rec)
            curr_state[key] = {"spaces": rec.get("spaces"), "free": free_now}

            prev = prev_state.get(key)
            if prev is not None and not prev.get("free") and free_now:
                newly_free.append(
                    f"{venue} {court} {today} {starts_at} ({rec.get('spaces')} space(s))"
                )

    if newly_free:
        body = "\n".join(newly_free)
        logging.info("Slot(s) opened up:\n%s", body)
        if not args.dry_run:
            notify("Tennis court free!", body)
    else:
        logging.info("Checked %d watched slot(s); no change.", len(curr_state))

    save_state(args.state_file, curr_state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
