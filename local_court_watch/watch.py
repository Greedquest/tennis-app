"""
Wednesday-evening court watch: poll localtenniscourts.com and alert (desktop
notification) the moment a Wednesday slot starting >= 19:00 flips from
booked to free. Alert only -- no booking automation.

Meant to be invoked every 5 minutes by cron/Tasker on the user's own machine
(a Claude Code cloud routine can't poll more often than hourly). Designed to
run unconditionally from cron and no-op outside the watch window, e.g.:

    */5 12-21 * * 3 /usr/bin/python3 -m local_court_watch.watch >> ~/.cache/court_watch.log 2>&1

See README.md in this directory for full cron / Termux setup.
"""

import argparse
import logging
import sys
from datetime import datetime

from local_court_watch import cache
from local_court_watch.notify import send_notification
from local_court_watch.parser import DEFAULT_QUERY, fetch_page, parse_today_slots

WEDNESDAY = 2
WATCH_START_HOUR = 12
WATCH_END_HOUR = 22
MIN_START_HOUR = 19

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Wednesday-evening tennis court watch")
    p.add_argument(
        "--cache", default="cache/court_watch_state.json", help="Path to the state cache file"
    )
    p.add_argument("--query", default=DEFAULT_QUERY, help="localtenniscourts.com ?q= venue query")
    p.add_argument("--force", action="store_true", help="Skip the Wednesday/time-window guard")
    p.add_argument("--no-notify", action="store_true", help="Disable notifications (for testing)")
    p.add_argument(
        "--html-file",
        default=None,
        help="Parse a saved HTML file instead of fetching live (for offline testing)",
    )
    return p.parse_args(argv)


def in_watch_window(now: datetime) -> bool:
    return now.weekday() == WEDNESDAY and WATCH_START_HOUR <= now.hour < WATCH_END_HOUR


def run(now: datetime, html: str, cache_path: str, *, notify: bool = True) -> int:
    today_iso = now.date().isoformat()
    slots = [s for s in parse_today_slots(html) if s.hour >= MIN_START_HOUR]

    current: dict[str, int] = {}
    by_key: dict[str, tuple[str, int]] = {}  # key -> (label, spaces) for alert messages
    for slot in slots:
        for venue in slot.venues:
            key = f"{slot.hour}|{venue.venue_id}"
            current[key] = venue.spaces
            by_key[key] = (f"{venue.name} {slot.from_time}", venue.spaces)

    previous = cache.load(cache_path, today_iso)

    opened = [key for key, spaces in current.items() if previous.get(key) == 0 and spaces > 0]

    if opened:
        lines = []
        for key in opened:
            label, spaces = by_key[key]
            venue_id = key.split("|")[1]
            slot = next(s for s in slots if any(v.venue_id == int(venue_id) for v in s.venues))
            venue = next(v for v in slot.venues if v.venue_id == int(venue_id))
            lines.append(f"{label}: {spaces} space(s) free\n{venue.booking_url}")
        message = "\n\n".join(lines)
        logging.info("Slot(s) opened up:\n%s", message)
        if notify:
            send_notification("Tennis court free tonight!", message)
    else:
        logging.info("Checked %d slot(s); no new openings.", len(current))

    cache.save(cache_path, today_iso, current)
    return len(opened)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    now = datetime.now()

    if not args.force and not in_watch_window(now):
        logging.info(
            "Outside the Wednesday %d:00-%d:00 watch window; skipping.",
            WATCH_START_HOUR,
            WATCH_END_HOUR,
        )
        return 0

    if args.html_file:
        with open(args.html_file, encoding="utf-8") as f:
            html = f.read()
    else:
        html = fetch_page(args.query)

    run(now, html, args.cache, notify=not args.no_notify)
    return 0


if __name__ == "__main__":
    sys.exit(main())
