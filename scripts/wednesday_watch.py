#!/usr/bin/env python3
"""Local Wednesday-evening court watch: Highbury Fields + ITC Outdoor.

Standalone script, deliberately independent of the ``tennis_app`` package
and its GitHub Actions poller. Per the brief this runs on: alert the moment
a slot starting at or after 19:00 on a Wednesday flips from booked to free.
Alert only — no booking automation.

Both watched courts turn out to be on the same Better Admin API this repo
already polls for Islington Tennis Centre (confirmed via
scripts/probe_ltc.py against localtenniscourts.com, whose scraped
booking_url for Highbury Fields is
``.../location/islington-tennis-centre/highbury-tennis/...``):

    islington-tennis-centre / highbury-tennis        (Highbury Fields)
    islington-tennis-centre / tennis-court-outdoor    (ITC Outdoor)

Why this is a separate script, not a GitHub Actions workflow:
  - The brief wants this to run locally (cron / Tasker / Termux), not as a
    cloud routine, so it can fire a desktop/mobile notification and so it
    isn't bound by the ~hourly minimum cadence of cloud-routine scheduling.
  - As of writing, the Better Admin API is returning 422 to every request
    from GitHub Actions IPs (checked via scripts/probe_venue.py, including
    on the long-standing "known-good" control pair) — every scheduled run
    of poller.yml has failed the same way for the last several days. A
    residential/mobile connection (this script's actual deployment target)
    is a different network path and may not be affected, but this means
    the highbury-tennis slug below could not be confirmed with a live 200
    response during development. Its correctness rests on matching this
    repo's own URL-building convention exactly (see tennis_app/transform.py)
    against the fresh booking_url the aggregator scraped. Verify it
    actually returns data the first time you run this for real.

Suggested crontab line (Wednesdays, midday-22:00, every 5 minutes; runs in
the user's local time zone):

    */5 12-21 * * 3 cd /path/to/tennis-app && python3 scripts/wednesday_watch.py
    55,56,57,58,59 21 * * 3 cd /path/to/tennis-app && python3 scripts/wednesday_watch.py

(cron has no "22:00 inclusive" shorthand; the second line covers the last
few minutes up to 22:00. Simplify to `12-22` if a few minutes of overrun
past 22:00 doesn't matter.)

Verify locally without notifying:
    python3 scripts/wednesday_watch.py --cache /tmp/ww_state.json --no-notify
    (run twice — the first run only establishes a baseline and stays silent)
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import Any

import requests

API = "https://better-admin.org.uk/api/activities/venue/{venue}/activity/{court}/times"

HEADERS = {
    "Origin": "https://bookings.better.org.uk",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://bookings.better.org.uk/",
}

WATCHED = [
    {"venue": "islington-tennis-centre", "court": "highbury-tennis", "label": "Highbury Fields"},
    {
        "venue": "islington-tennis-centre",
        "court": "tennis-court-outdoor",
        "label": "Islington Tennis Centre - Outdoor",
    },
]

WATCH_WEEKDAY = 2  # Monday=0 ... Wednesday=2
WATCH_HOUR_FROM = 19

DEFAULT_CACHE_PATH = "cache/wednesday_watch_state.json"
DEFAULT_DAYS_AHEAD = 8  # always covers the next Wednesday regardless of today
REQUEST_DELAY = 1.5  # seconds between requests; Better Admin rate-limits bursts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def fetch_activities(venue: str, court: str, date: str) -> list[dict[str, Any]]:
    """Fetch one venue/court/date's raw activity records from the Better Admin API."""
    url = API.format(venue=venue, court=court)
    r = requests.get(url, headers=HEADERS, params={"date": date}, timeout=15)
    r.raise_for_status()
    data = r.json().get("data", [])
    return list(data.values()) if isinstance(data, dict) else data


def fetch_watched_window(days_ahead: int = DEFAULT_DAYS_AHEAD) -> list[dict[str, Any]]:
    """Fetch every watched venue/court for the next ``days_ahead`` days."""
    today = datetime.now().date()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_ahead)]

    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for target in WATCHED:
        for date in dates:
            try:
                for rec in fetch_activities(target["venue"], target["court"], date):
                    rec["venue"] = target["venue"]
                    rec["court"] = target["court"]
                    rec["venue_label"] = target["label"]
                    records.append(rec)
            except Exception as e:  # noqa: BLE001 - log and keep polling other dates
                errors.append(f"{target['venue']}/{target['court']} {date}: {e}")
                logging.warning("Fetch failed for %s/%s on %s: %s", target["venue"], target["court"], date, e)
            time.sleep(REQUEST_DELAY)

    if errors and not records:
        raise RuntimeError(f"All {len(errors)} fetch attempt(s) failed. First error: {errors[0]}")
    return records


def filter_watch_window(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only Wednesday slots starting at or after WATCH_HOUR_FROM."""
    kept = []
    for rec in records:
        date_str = rec.get("date")
        starts_at = rec.get("starts_at") or {}
        hour_str = starts_at.get("format_24_hour")
        if not date_str or not hour_str:
            continue
        try:
            weekday = datetime.strptime(date_str, "%Y-%m-%d").weekday()
            hour = int(hour_str.split(":")[0])
        except ValueError:
            continue
        if weekday == WATCH_WEEKDAY and hour >= WATCH_HOUR_FROM:
            kept.append(rec)
    return kept


def key_of(rec: dict[str, Any]) -> str:
    starts_at = rec.get("starts_at") or {}
    return f"{rec.get('date')}|{starts_at.get('format_24_hour')}|{rec.get('venue')}/{rec.get('court')}"


def to_state(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Reduce watch-window records to {key: {spaces, label, time_12h, url}} for caching/diffing."""
    state = {}
    for rec in records:
        starts_at = rec.get("starts_at") or {}
        ends_at = rec.get("ends_at") or {}
        state[key_of(rec)] = {
            "spaces": rec.get("spaces") or 0,
            "venue_label": rec.get("venue_label"),
            "date": rec.get("date"),
            "time_12h": starts_at.get("format_12_hour"),
            "booking_url": (
                f"https://bookings.better.org.uk/location/{rec.get('venue')}/{rec.get('court')}/"
                f"{rec.get('date')}/by-time/slot/{starts_at.get('format_24_hour')}-{ends_at.get('format_24_hour')}"
            ),
        }
    return state


def newly_free_keys(prev: dict[str, dict[str, Any]], curr: dict[str, dict[str, Any]]) -> list[str]:
    """Keys present in both polls where spaces went from <=0 to >0.

    Keys with no prior baseline are not alerted — a cold cache (first run,
    or a lost cache file) has nothing to compare against and should stay
    silent rather than alert on every slot that merely already had spaces.
    """
    return [
        key
        for key, curr_val in curr.items()
        if key in prev and prev[key].get("spaces", 0) <= 0 and curr_val.get("spaces", 0) > 0
    ]


def load_state(path: str) -> dict[str, dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(path: str, state: dict[str, dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def notify_local(title: str, message: str) -> None:
    """Best-effort desktop/mobile notification: Termux, then Linux, then macOS, then a log line."""
    if shutil.which("termux-notification"):
        subprocess.run(["termux-notification", "--title", title, "--content", message], check=False)
        return
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False)
        return
    if shutil.which("osascript"):
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False)
        return
    logging.warning("No notification backend found; alert follows: %s — %s", title, message)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Wednesday-evening Highbury Fields / ITC Outdoor watch.")
    p.add_argument("--cache", default=DEFAULT_CACHE_PATH, help="Path to the local state cache file.")
    p.add_argument("--days", type=int, default=DEFAULT_DAYS_AHEAD, help="Days ahead to fetch.")
    p.add_argument("--no-notify", action="store_true", help="Skip the desktop notification (for testing).")
    args = p.parse_args(argv)

    raw_records = fetch_watched_window(args.days)
    watch_records = filter_watch_window(raw_records)
    curr_state = to_state(watch_records)
    prev_state = load_state(args.cache)

    changed = newly_free_keys(prev_state, curr_state)
    if changed:
        lines = []
        for key in changed:
            slot = curr_state[key]
            lines.append(f"{slot['venue_label']} {slot['date']} {slot['time_12h']} — {slot['spaces']} space(s)")
        message = "\n".join(lines)
        logging.info("%d slot(s) just opened up:\n%s", len(changed), message)
        if not args.no_notify:
            notify_local("Tennis court free!", message)
    else:
        logging.info("Checked %d watched Wednesday-evening slot(s); no change.", len(curr_state))

    save_state(args.cache, curr_state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
