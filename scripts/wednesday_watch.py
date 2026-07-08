#!/usr/bin/env python3
"""Local Wednesday-evening court watch: alert only, no booking.

Standalone script meant to run from a local cron job (or Termux/Tasker),
NOT from a Claude Code routine or this repo's GitHub Actions poller —
those only run hourly-or-slower / every-minute-in-the-cloud respectively,
neither of which fits "poll every 5 minutes, Wednesday afternoons only,
notify via a local desktop/phone notification."

What it does:
  1. Fetch upcoming slots for the configured venues via the same Better
     Admin API integration tennis_app already uses (see tennis_app/fetch.py).
  2. Keep only Wednesday slots starting at or after 19:00.
  3. Compare each slot's space count against the last local run. If a slot
     had 0 spaces last run and has >0 spaces now, that's a booked -> free
     flip: fire a desktop notification.
  4. Save current state for the next run. First run ever (no cache) never
     alerts -- there's nothing to compare against yet.

Run it directly, or on a schedule (see README section "Wednesday watch"
for a crontab / Termux example). Intended usage from the repo root:

    PYTHONPATH=. python scripts/wednesday_watch.py

Non-goal: this never books anything. It only notifies.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tennis_app.fetch import fetch_activities  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

WEDNESDAY = 2  # datetime.weekday(): Monday=0 ... Sunday=6
CUTOFF_HOUR = 19

# Confirmed, working venue/court slugs (same as tennis_app/config.py).
# Highbury Fields (islington-parks) is NOT included: per CLAUDE.md its
# venue/court slug isn't confirmed yet (candidates return 200-with-zero-
# records, which doesn't distinguish "right slug, nothing free" from
# "wrong slug"). Add it here once scripts/probe_venue.py confirms one.
VENUES = [
    {"venue": "islington-tennis-centre", "court": "tennis-court-indoor"},
    {"venue": "islington-tennis-centre", "court": "tennis-court-outdoor"},
]

DEFAULT_CACHE_PATH = os.path.expanduser("~/.cache/tennis-app/wednesday-watch-state.json")


def slot_key(venue: str, court: str, date_str: str, time_24h: str) -> str:
    return f"{venue}|{court}|{date_str}|{time_24h}"


def fetch_wednesday_evening_slots(venues: list[dict[str, str]], days_ahead: int = 9) -> dict[str, dict]:
    """Fetch upcoming activities and keep only Wednesday slots >= 19:00.

    Returns a dict of slot_key -> {spaces, venue, court, date, time, url}.
    """
    today = date.today()
    dates = [(today + timedelta(days=i)) for i in range(days_ahead)]
    wednesday_dates = [d for d in dates if d.weekday() == WEDNESDAY]

    slots: dict[str, dict] = {}
    for vc in venues:
        venue, court = vc["venue"], vc["court"]
        for d in wednesday_dates:
            date_str = d.strftime("%Y-%m-%d")
            try:
                activities = fetch_activities(venue, court, date_str)
            except Exception as e:  # noqa: BLE001
                logging.warning("Fetch failed for %s/%s on %s: %s", venue, court, date_str, e)
                continue

            for a in activities:
                starts_at = a.get("starts_at") or {}
                time_24h = starts_at.get("format_24_hour")
                if not time_24h:
                    continue
                hour = int(time_24h.split(":")[0])
                if hour < CUTOFF_HOUR:
                    continue

                key = slot_key(venue, court, date_str, time_24h)
                slots[key] = {
                    "venue": venue,
                    "court": court,
                    "date": date_str,
                    "time": starts_at.get("format_12_hour", time_24h),
                    "spaces": a.get("spaces"),
                    "url": (
                        f"https://bookings.better.org.uk/location/{venue}/{court}/"
                        f"{date_str}/by-time/slot/{time_24h}-{(a.get('ends_at') or {}).get('format_24_hour', '')}"
                    ),
                }
    return slots


def load_state(cache_path: str) -> dict:
    try:
        with open(cache_path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(cache_path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    tmp = cache_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, cache_path)


def find_newly_free(prev: dict, curr: dict) -> list[dict]:
    """Slots that had 0 spaces last run and have >0 spaces now."""
    newly_free = []
    for key, slot in curr.items():
        prev_slot = prev.get(key)
        if prev_slot is None:
            continue  # no baseline for this slot yet; not a "flip"
        prev_spaces = prev_slot.get("spaces") or 0
        curr_spaces = slot.get("spaces") or 0
        if prev_spaces == 0 and curr_spaces > 0:
            newly_free.append(slot)
    return newly_free


def notify(title: str, message: str) -> None:
    """Best-effort desktop/phone notification. Tries, in order:
    plyer (cross-platform), termux-notification (Termux/Android),
    notify-send (Linux), osascript (macOS). Falls back to a log line.
    """
    try:
        from plyer import notification as plyer_notification

        plyer_notification.notify(title=title, message=message)
        return
    except Exception:  # noqa: BLE001
        pass

    if shutil.which("termux-notification"):
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

    logging.warning("No notification backend available; alert was: %s - %s", title, message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", default=DEFAULT_CACHE_PATH, help="Path to local state file")
    parser.add_argument(
        "--no-notify", action="store_true", help="Skip sending a notification (for testing)"
    )
    args = parser.parse_args(argv)

    now = datetime.now()
    logging.info("Checking Wednesday >=19:00 slots at %s", now.isoformat(timespec="seconds"))

    curr = fetch_wednesday_evening_slots(VENUES)
    prev = load_state(args.cache)

    newly_free = find_newly_free(prev, curr)

    if newly_free:
        lines = [f"{s['date']} {s['time']} - {s['venue']}/{s['court']}" for s in newly_free]
        message = "\n".join(lines)
        logging.info("Newly free slot(s):\n%s", message)
        if not args.no_notify:
            notify("Tennis court free Wednesday!", message)
    else:
        logging.info("No newly-free Wednesday evening slots. Quiet run.")

    save_state(args.cache, curr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
