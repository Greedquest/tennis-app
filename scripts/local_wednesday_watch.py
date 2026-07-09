#!/usr/bin/env python3
"""Local Wednesday-evening court watch for localtenniscourts.com.

Standalone, no dependency on the tennis_app package (different source site,
different alert channel, different execution model). Meant to run from a
local cron job or Termux/Tasker, NOT as a Claude Code cloud routine: routines
are hourly-minimum, this needs 5-minute cadence.

What it does
------------
1. Fetches https://localtenniscourts.com/?q=<venues> (server-rendered HTML;
   there's no separate JSON API — confirmed by probing the built JS bundles
   and common /api/* guesses, all 404/absent). The page always renders a
   rolling "today + 5 days" table, so as long as this only runs on
   Wednesdays, today's column is always present -- no date-navigation logic
   needed.
2. Parses the availability table into (date, time, available) slots.
3. Filters to today's slots starting at or after 19:00 (only meaningful when
   run on a Wednesday).
4. Diffs against the previous poll (local JSON cache). Any slot flipping
   booked -> free fires a desktop notification.
5. Alert only. No booking automation.

Cell format (observed): a booked/unavailable cell renders literal "-" text
in a `bg-red-*` cell; anything else (a time/price/booking link) is treated
as available. If localtenniscourts.com changes its markup this heuristic
may need updating -- run with --dump-html to capture a fresh sample.

Scheduling
----------
The script is cheap to run wastefully, but the brief calls for Wednesday
midday-22:00 only, every 5 minutes. It also self-guards (skip silently
outside that window unless --force), so a misconfigured scheduler is
harmless.

crontab (Linux/local box):
    */5 12-21 * * 3 /usr/bin/python3 /path/to/local_wednesday_watch.py
    # (hour 22:00 itself is the boundary; 12-21 covers 12:00-21:5x)

Termux + Tasker (Android, per existing setup):
    - Install Termux + Termux:API (for `termux-notification`).
    - `pip install requests beautifulsoup4` inside Termux.
    - Use Tasker's "Run Termux command" or Termux:Crond
      (`pkg install termux-crond`) with the same crontab line above.
    - termux-notification is auto-detected; no extra flags needed.

Verify without waiting for Wednesday:
    python3 scripts/local_wednesday_watch.py --once --force --state-path /tmp/ltc_state.json
    (run twice against a manually-edited state file to exercise the diff path)
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://localtenniscourts.com/"
DEFAULT_QUERY = "highbury-fields,islington-tennis-centre-outdoor"
DEFAULT_STATE_PATH = Path.home() / ".cache" / "tennis_watch" / "state.json"
MIN_HOUR = "19:00"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

DAY_ABBR_TO_WEEKDAY = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("wednesday_watch")


@dataclass(frozen=True)
class Slot:
    d: date
    time: str
    available: bool

    @property
    def key(self) -> str:
        return f"{self.d.isoformat()}|{self.time}"


def fetch_page(query: str) -> str:
    r = requests.get(BASE_URL, params={"q": query}, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def _resolve_column_date(day_abbr: str, day_num: int, today: date) -> date:
    """Map a 'Thu 09'-style header to a real date, anchored on `today`."""
    for delta in range(0, 10):
        candidate = today + timedelta(days=delta)
        if candidate.day == day_num:
            return candidate
    # Fallback: trust the weekday name over the day number if nothing matched
    # within 10 days (shouldn't happen given the site's 6-day window).
    raise ValueError(f"Could not resolve column '{day_abbr} {day_num:02d}' near {today}")


def parse_slots(html: str, today: date) -> list[Slot]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise ValueError("No <table> found in page — site markup may have changed")

    header_cells = table.find("thead").find_all("th")[1:]  # skip "Time" column
    columns: list[date] = []
    for th in header_cells:
        text = th.get_text(strip=True)  # e.g. "Thu 09"
        abbr, num = text.split()
        columns.append(_resolve_column_date(abbr, int(num), today))

    slots: list[Slot] = []
    for row in table.find("tbody").find_all("tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        time_str = cells[0].get_text(strip=True)
        for col_date, cell in zip(columns, cells[1:]):
            cell_text = cell.get_text(strip=True)
            available = cell_text != "-" and cell_text != ""
            slots.append(Slot(d=col_date, time=time_str, available=available))
    return slots


def filter_target(slots: list[Slot], today: date) -> list[Slot]:
    return [s for s in slots if s.d == today and s.time >= MIN_HOUR]


def load_state(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Could not read state file %s (%s); starting fresh.", path, e)
        return {}


def save_state(path: Path, state: dict[str, bool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True))


def notify(message: str) -> None:
    if shutil.which("termux-notification"):
        subprocess.run(
            ["termux-notification", "--title", "Court available!", "--content", message],
            check=False,
        )
        return
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "Court available!", message], check=False)
        return
    if shutil.which("osascript"):
        script = f'display notification "{message}" with title "Court available!"'
        subprocess.run(["osascript", "-e", script], check=False)
        return
    log.warning("No desktop notifier found (termux-notification/notify-send/osascript). "
                "Falling back to console:")
    print(f"*** COURT AVAILABLE: {message} ***")


def within_watch_window(now: datetime, force: bool) -> bool:
    if force:
        return True
    if now.weekday() != DAY_ABBR_TO_WEEKDAY["Wed"]:
        log.info("Not Wednesday (weekday=%d); skipping.", now.weekday())
        return False
    if not ("12:00" <= now.strftime("%H:%M") <= "22:00"):
        log.info("Outside 12:00-22:00 watch window (%s); skipping.", now.strftime("%H:%M"))
        return False
    return True


def run_once(query: str, state_path: Path, do_notify: bool, force: bool, dump_html: Path | None) -> None:
    now = datetime.now()
    if not within_watch_window(now, force):
        return

    log.info("Fetching %s?q=%s", BASE_URL, query)
    html = fetch_page(query)
    if dump_html:
        dump_html.write_text(html)
        log.info("Dumped raw HTML to %s", dump_html)

    today = now.date()
    all_slots = parse_slots(html, today)
    target = filter_target(all_slots, today)
    log.info("Parsed %d slots total; %d in today's >=%s window.", len(all_slots), len(target), MIN_HOUR)

    prev_state = load_state(state_path)
    newly_free = []
    for slot in target:
        was_available = prev_state.get(slot.key)
        if was_available is False and slot.available:
            newly_free.append(slot)

    if newly_free:
        msg = "; ".join(f"{s.time}" for s in sorted(newly_free, key=lambda s: s.time))
        log.info("ALERT: newly free slot(s) at %s", msg)
        if do_notify:
            notify(f"Wednesday {today.isoformat()} — free at {msg}")
    else:
        log.info("No newly-freed slots; quiet.")

    curr_state = {**prev_state, **{s.key: s.available for s in target}}
    save_state(state_path, curr_state)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--query", default=DEFAULT_QUERY, help="localtenniscourts.com 'q' param (comma-separated venue slugs)")
    p.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    p.add_argument("--once", action="store_true", help="Run a single check and exit (default; kept for clarity)")
    p.add_argument("--no-notify", action="store_true", help="Log only, skip the desktop notification")
    p.add_argument("--force", action="store_true", help="Bypass the Wednesday/12:00-22:00 guard, for testing")
    p.add_argument("--dump-html", type=Path, default=None, help="Save the fetched HTML to this path for inspection")
    args = p.parse_args(argv)

    try:
        run_once(
            query=args.query,
            state_path=args.state_path,
            do_notify=not args.no_notify,
            force=args.force,
            dump_html=args.dump_html,
        )
    except requests.RequestException as e:
        log.error("Fetch failed: %s", e)
        return 1
    except ValueError as e:
        log.error("Parse failed: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
