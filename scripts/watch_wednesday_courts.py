#!/usr/bin/env python3
"""Wednesday-evening court watch for localtenniscourts.com.

Polls the Highbury Fields / Islington Tennis Centre (outdoor) availability
page and alerts the moment a slot starting at or after 19:00 *today*
flips from booked to free. Meant to be invoked by cron (or Termux's
crond/Tasker) every 5 minutes; the script itself no-ops quietly outside
Wednesday midday-to-22:00, so a looser cron schedule is fine.

Why this is a standalone script and not a Claude Code routine: routines
run hourly at best, and this needs 5-minute granularity. Why not part of
the `tennis_app` package: that package polls a different site (the Better
Admin booking API) on a different schedule for different venues.

Data source: the page is fully server-rendered HTML - a plain GET already
returns the populated availability table, no client-side JSON API to
call (confirmed: zero XHR/fetch requests fire when loading the page in a
real browser). The leftmost day column in the table is always "today",
so on a Wednesday-only routine that column is always Wednesday - no need
to page forward to a future date.

Setup:
    pip install requests beautifulsoup4
    # optional, for a desktop notification fallback when not on Termux:
    pip install plyer

Cron (every 5 min, Wednesdays only - the script's own time-window check
narrows this down to midday-22:00, so the cron expression itself can be
loose):
    */5 * * * 3 /usr/bin/python3 /path/to/watch_wednesday_courts.py

Termux (crond via `pkg install cronie`, or a Tasker profile that shells
out to `termux-job-scheduler` / runs this directly): same command, and
install `termux-api` + the Termux:API app for `termux-notification`.

Verify without waiting for Wednesday or for a real change:
    python scripts/watch_wednesday_courts.py --force --dry-run --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"
DEFAULT_STATE_PATH = os.path.expanduser("~/.cache/wed_watch/state.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; wed-watch/1.0)"}


def in_watch_window(now: datetime) -> bool:
    """Wednesday, midday to 22:00 - matches the brief's polling window."""
    return now.weekday() == 2 and 12 <= now.hour < 22  # Monday=0 -> Wednesday=2


def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.text


def parse_today_slots(html: str) -> dict[str, int]:
    """
    Parse the availability table and return {time_str: free_courts} for
    the "today" (leftmost) day column, e.g. {"19:00": 0, "19:30": 2, ...}.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise ValueError("No <table> found on the page; site layout may have changed")

    rows = table.find_all("tr")
    if not rows:
        raise ValueError("Table has no rows")

    header_cells = rows[0].find_all(["th", "td"])
    today_index = None
    for i, cell in enumerate(header_cells[1:], start=1):
        if cell.get_text(strip=True).startswith("Wed"):
            today_index = i
            break
    if today_index is None:
        raise ValueError("Could not find a 'Wed' column in the table header")

    slots: dict[str, int] = {}
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) <= today_index:
            continue
        time_text = cells[0].get_text(strip=True)
        if not re.match(r"^\d{1,2}:\d{2}$", time_text):
            continue
        cell_text = cells[today_index].get_text(separator=" ", strip=True)
        if cell_text == "-" or not cell_text:
            slots[time_text] = 0
        else:
            m = re.match(r"^(\d+)", cell_text)
            slots[time_text] = int(m.group(1)) if m else 0

    return slots


def load_state(path: str) -> dict[str, int]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(path: str, state: dict[str, int]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


def notify(title: str, message: str) -> None:
    if shutil.which("termux-notification"):
        subprocess.run(
            ["termux-notification", "--title", title, "--content", message],
            check=False,
        )
        return
    try:
        from plyer import notification as plyer_notification

        plyer_notification.notify(title=title, message=message, timeout=15)
        return
    except Exception:
        logging.info("No notification backend available; logging alert instead.")
    logging.warning("ALERT: %s - %s", title, message)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Wednesday-evening court watch")
    p.add_argument("--url", default=URL)
    p.add_argument("--state", default=DEFAULT_STATE_PATH)
    p.add_argument(
        "--min-hour",
        type=int,
        default=19,
        help="Only alert on slots starting at or after this hour (default 19)",
    )
    p.add_argument(
        "--force", action="store_true", help="Skip the Wednesday/midday-22:00 time-window check"
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Detect changes but don't send a notification"
    )
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    now = datetime.now()
    if not args.force and not in_watch_window(now):
        logging.info("Outside the Wednesday midday-22:00 watch window; skipping.")
        return 0

    try:
        html = fetch_html(args.url)
        current = parse_today_slots(html)
    except Exception as e:
        logging.warning("Fetch/parse failed: %s", e)
        return 1

    watched = {t: n for t, n in current.items() if int(t.split(":")[0]) >= args.min_hour}
    previous = load_state(args.state)

    newly_freed = [t for t, n in watched.items() if n > 0 and previous.get(t, 0) == 0]

    if newly_freed:
        message = ", ".join(
            f"{t} ({watched[t]} court{'s' if watched[t] != 1 else ''})" for t in sorted(newly_freed)
        )
        logging.info("Slot(s) opened up: %s", message)
        if not args.dry_run:
            notify("Tennis court available", message)
    else:
        logging.info("No change in watched slots (%d checked).", len(watched))

    save_state(args.state, current)
    return 0


if __name__ == "__main__":
    sys.exit(main())
