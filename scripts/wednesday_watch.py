#!/usr/bin/env python3
"""Local Wednesday-evening court watch.

Standalone, LOCAL-ONLY script — deliberately separate from the cloud GH
Actions poller in this repo (.github/workflows/poller.yml). Claude Code
routines and GitHub Actions schedules are hourly-minimum, too coarse for a
5-minute check, so this alert has to run from a local cron job, Termux job
scheduler, or a lightweight always-on process instead (see --loop below).

Behaviour:
  - Fetches Wednesday's availability for Highbury Fields and Islington
    Tennis Centre (outdoor) directly from the Better Admin API — the same
    API tennis_app/fetch.py already uses for the cloud poller, and far
    more robust than scraping a third-party aggregator's rendered page.
  - Filters to slots starting at or after 19:00.
  - Compares against the previous run's snapshot (local JSON state file).
  - Fires a local notification the moment a slot flips from booked
    (0 spaces) to free (>0 spaces). Silent otherwise — no alert unless
    something changed.
  - Never books anything. Alert only; you book manually.

Highbury Fields' Better Admin slug (`islington-parks`/`tennis-court-outdoor`)
is structurally valid (the API returns 200, not 404) but hadn't shown any
populated records as of the last check — Better Admin only publishes a
rolling booking window, so this may just mean nothing's open yet within
that window. If it never populates, the court slug may actually be
`highbury-fields-activities` instead; re-probe with
scripts/probe_venue.py if Highbury Fields alerts never fire.

Schedule with cron, Wednesdays only, midday to 22:00, every 5 minutes:
    */5 12-21 * * 3 cd /path/to/tennis-app && python3 scripts/wednesday_watch.py >> logs/wednesday_watch.log 2>&1
    0   22    * * 3 cd /path/to/tennis-app && python3 scripts/wednesday_watch.py >> logs/wednesday_watch.log 2>&1

On Termux (Android): `pkg install cronie termux-api`, then the same two
crontab lines give you termux-notification alerts. Prefer Tasker/
Termux:Widget instead of cron? Just point either at the same command —
each invocation does one check and exits.

Don't want to manage a schedule at all? Run with --loop and leave it
running in a terminal/tmux session; it sleeps between checks and only
checks during the Wednesday midday-22:00 window.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tennis_app.fetch import fetch_activities  # noqa: E402

VENUES = [
    {"venue": "islington-parks", "court": "tennis-court-outdoor", "label": "Highbury Fields"},
    {
        "venue": "islington-tennis-centre",
        "court": "tennis-court-outdoor",
        "label": "Islington Tennis Centre (outdoor)",
    },
]

MIN_START_HOUR = 19
WATCH_START_HOUR = 12
WATCH_END_HOUR = 22
POLL_SECONDS = 5 * 60

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_STATE_PATH = os.path.join(REPO_ROOT, "cache", "wednesday_watch_state.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def next_wednesday(today: date) -> date:
    """Return today if it's Wednesday, otherwise the coming Wednesday."""
    days_ahead = (2 - today.weekday()) % 7  # Monday=0 ... Wednesday=2
    return today + timedelta(days=days_ahead)


def in_watch_window(now: datetime) -> bool:
    return now.weekday() == 2 and WATCH_START_HOUR <= now.hour < WATCH_END_HOUR


def fetch_wednesday_evening_slots(target_date: date) -> list[dict]:
    """Fetch and filter to Wednesday slots starting at/after MIN_START_HOUR."""
    date_str = target_date.strftime("%Y-%m-%d")
    slots = []
    for v in VENUES:
        try:
            records = fetch_activities(v["venue"], v["court"], date_str)
        except Exception as e:
            logging.warning("Fetch failed for %s/%s on %s: %s", v["venue"], v["court"], date_str, e)
            continue
        for rec in records:
            starts_at = rec.get("starts_at") or {}
            time_24h = starts_at.get("format_24_hour")
            if not time_24h:
                continue
            hour = int(time_24h.split(":")[0])
            if hour < MIN_START_HOUR:
                continue
            slots.append(
                {
                    "key": f"{date_str}|{time_24h}|{v['label']}",
                    "date": date_str,
                    "time": starts_at.get("format_12_hour") or time_24h,
                    "venue": v["label"],
                    "spaces": rec.get("spaces") or 0,
                }
            )
    return slots


def load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def notify(title: str, message: str) -> None:
    """Best-effort local notification: Termux, then notify-send, then osascript."""
    if os.environ.get("TERMUX_VERSION") and shutil.which("termux-notification"):
        subprocess.run(
            ["termux-notification", "--title", title, "--content", message], check=False
        )
        return
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False)
        return
    if shutil.which("osascript"):
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False)
        return
    logging.warning("No notification backend found (termux-notification/notify-send/osascript); printing instead.")
    print(f"\a{title}: {message}")


def check_once(state_path: str) -> None:
    today = date.today()
    target = next_wednesday(today)
    logging.info("Checking Wednesday %s (slots >= %02d:00)...", target.isoformat(), MIN_START_HOUR)

    slots = fetch_wednesday_evening_slots(target)
    prev_state = load_state(state_path)

    newly_free = []
    curr_state = {}
    for slot in slots:
        curr_state[slot["key"]] = slot["spaces"]
        was_booked = prev_state.get(slot["key"], 0) == 0
        is_free = slot["spaces"] > 0
        if was_booked and is_free:
            newly_free.append(slot)

    if newly_free:
        lines = [f"{s['venue']} {s['time']} ({s['spaces']} space(s))" for s in newly_free]
        message = "\n".join(lines)
        logging.info("ALERT: %d slot(s) opened up:\n%s", len(newly_free), message)
        notify("Tennis court free!", message)
    else:
        logging.info("No change: %d slot(s) checked, none newly free.", len(slots))

    save_state(state_path, curr_state)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Alert when a Wednesday-evening (>=19:00) tennis slot opens up. Alert only, never books."
    )
    p.add_argument("--state", default=DEFAULT_STATE_PATH, help="Path to local JSON state file.")
    p.add_argument(
        "--loop",
        action="store_true",
        help="Run indefinitely, checking every 5 minutes during the Wednesday "
        f"{WATCH_START_HOUR}:00-{WATCH_END_HOUR}:00 window, instead of a single cron-style check.",
    )
    args = p.parse_args(argv)

    if not args.loop:
        check_once(args.state)
        return 0

    logging.info(
        "Looping: checking every %ds during Wednesday %d:00-%d:00. Ctrl+C to stop.",
        POLL_SECONDS,
        WATCH_START_HOUR,
        WATCH_END_HOUR,
    )
    try:
        while True:
            now = datetime.now()
            if in_watch_window(now):
                check_once(args.state)
                time.sleep(POLL_SECONDS)
            else:
                logging.info("Outside the Wednesday watch window; sleeping.")
                time.sleep(60)
    except KeyboardInterrupt:
        logging.info("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
