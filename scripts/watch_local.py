#!/usr/bin/env python3
"""Local Wednesday-evening court watch: desktop notification, no cloud dependency.

Companion to the GitHub Actions poller (.github/workflows/poller.yml), which
alerts by email. Use this instead when you'd rather get a push/desktop
notification on your own machine or phone, without touching GH Actions
secrets. Alert-only — it never books anything.

Setup (cron, every 5 minutes — the script gates on the Wednesday
noon-22:00 local watch window itself, so a plain */5 line is enough):

    */5 * * * * cd /path/to/tennis-app && PYTHONPATH=. python3 scripts/watch_local.py >> /tmp/tennis-watch.log 2>&1

On Termux (Android): same crontab line via `pkg install cronie termux-services`
+ `crontab -e`, or trigger from Tasker on a 5-minute interval instead.

Notification channel: tries termux-notification, then notify-send, then
osascript, whichever is on PATH; falls back to a log line if none are found.
"""

import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis_app.cache import load_prev_rows, save_rows  # noqa: E402
from tennis_app.config import WATCH_HOUR_FROM, WATCH_WEEKDAY  # noqa: E402
from tennis_app.fetch import fetch_all_activities  # noqa: E402
from tennis_app.transform import (  # noqa: E402
    filter_watch_window,
    newly_available_slots,
    tabularise,
)

LOCAL_CACHE_PATH = str(Path(__file__).resolve().parent.parent / "cache" / "local_state.json")
WINDOW_START_HOUR = 12
WINDOW_END_HOUR = 22


def _in_watch_window(now: datetime) -> bool:
    return now.weekday() == WATCH_WEEKDAY and WINDOW_START_HOUR <= now.hour < WINDOW_END_HOUR


def notify_desktop(title: str, message: str) -> None:
    if shutil.which("termux-notification"):
        subprocess.run(["termux-notification", "--title", title, "--content", message], check=False)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False)
    elif shutil.which("osascript"):
        # Escape for AppleScript string literals: backslash first, then quotes.
        def _as_escape(s: str) -> str:
            return s.replace("\\", "\\\\").replace('"', '\\"')

        script = f'display notification "{_as_escape(message)}" with title "{_as_escape(title)}"'
        subprocess.run(["osascript", "-e", script], check=False)
    else:
        logging.warning(
            "No desktop notifier found (tried termux-notification, notify-send, osascript)."
        )
    logging.info("ALERT: %s — %s", title, message)


def main() -> int:
    now = datetime.now()
    if not _in_watch_window(now):
        logging.info(
            "Outside the Wednesday %d:00-%d:00 watch window; skipping.",
            WINDOW_START_HOUR,
            WINDOW_END_HOUR,
        )
        return 0

    logging.info("Fetching activities…")
    raw_records = fetch_all_activities()
    curr_df = tabularise(raw_records)
    prev_df = load_prev_rows(LOCAL_CACHE_PATH)

    watched_curr = filter_watch_window(curr_df, WATCH_WEEKDAY, WATCH_HOUR_FROM)
    watched_prev = filter_watch_window(prev_df, WATCH_WEEKDAY, WATCH_HOUR_FROM)
    newly_free = newly_available_slots(watched_curr, watched_prev)

    if not newly_free.is_empty():
        rows = newly_free.to_dicts()
        summary = "; ".join(f"{r['Date']} {r['Time']} @ {r['Venue']}" for r in rows)
        notify_desktop("Tennis slot open!", summary)
    else:
        logging.info("No newly-available watched slots.")

    save_rows(LOCAL_CACHE_PATH, curr_df)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(main())
