#!/usr/bin/env python3
"""Local cron entrypoint: alert when a >=19:00 Wednesday slot flips booked -> free.

Not part of the cloud pipeline (see tennis_app/pipeline.py + .github/workflows/poller.yml).
Run this locally on a 5-minute cron (or Termux + Tasker), Wednesdays, midday to 22:00 -- see
docs/wednesday_watch.md for the crontab line and setup notes.

    PYTHONPATH=. python scripts/wednesday_watch.py
    PYTHONPATH=. python scripts/wednesday_watch.py --force --dry-run   # manual test, any day
"""

import argparse
import logging
import sys
from datetime import datetime

from tennis_app.wednesday_watch import (
    DEFAULT_URL,
    MIN_HOUR,
    WEDNESDAY,
    SlotParseError,
    extract_slots,
    fetch_html,
    filter_wednesday_evening,
    load_cache,
    newly_freed,
    notify,
    save_cache,
)

DEFAULT_CACHE = "cache/wednesday_state.json"
WINDOW_START_HOUR = 12
WINDOW_END_HOUR = 22


def _in_window(now: datetime) -> bool:
    return now.weekday() == WEDNESDAY and WINDOW_START_HOUR <= now.hour < WINDOW_END_HOUR


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--cache", default=DEFAULT_CACHE)
    p.add_argument("--min-hour", type=int, default=MIN_HOUR)
    p.add_argument(
        "--force",
        action="store_true",
        help="Run even outside the Wednesday midday-22:00 window (for manual testing).",
    )
    p.add_argument("--dry-run", action="store_true", help="Skip the notification, just log.")
    args = p.parse_args(argv)

    now = datetime.now()
    if not args.force and not _in_window(now):
        logging.info("Outside the Wednesday watch window; skipping quietly.")
        return 0

    try:
        html = fetch_html(args.url)
        slots = extract_slots(html)
    except SlotParseError as e:
        logging.error("%s", e)
        return 1
    except Exception:
        logging.exception("Fetch failed")
        return 1

    curr = filter_wednesday_evening(slots, min_hour=args.min_hour)
    prev = load_cache(args.cache)

    freed = newly_freed(prev, curr)
    if freed:
        message = "\n".join(f"{s.start:%H:%M} {s.venue}/{s.court}" for s in freed)
        logging.info("Newly free: %s", message)
        if not args.dry_run:
            notify("Tennis court free!", message)
    else:
        logging.info("Checked %d Wednesday-evening slot(s); no change.", len(curr))

    save_cache(args.cache, curr)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(main())
