#!/usr/bin/env python3
"""Wednesday-evening Highbury Fields court watch.

Standalone, LOCALLY-scheduled monitor (cron / Termux+Tasker) -- deliberately
NOT wired into the GitHub Actions poller or any Claude Code routine. Claude
Code routines run no more often than hourly, and this needs a 5-minute
cadence on Wednesday afternoons/evenings only, so schedule it yourself:

    # crontab -e  (day-of-week 3 = Wednesday)
    */5 12-21 * * 3 /usr/bin/python3 /path/to/highbury_wednesday_watch.py
    0   22    * * 3 /usr/bin/python3 /path/to/highbury_wednesday_watch.py

Source: https://localtenniscourts.com/?q=highbury-fields

  - No JSON API: confirmed via a throwaway GitHub Actions probe (this
    sandbox's proxy blocks the site directly) that the page is plain
    server-rendered HTML -- a single ``requests.get`` already returns the
    fully populated availability table. Scraping is not a fallback here,
    it's the only option.
  - Only "highbury-fields" is a valid slug on THIS site. The brief's
    combined query (``?q=highbury-fields,islington-tennis-centre-outdoor``)
    was probed too: it silently ignores the unrecognised second slug and
    returns identical output to the Highbury-only query. Querying
    ``islington-tennis-centre-outdoor`` alone returns an "Oops!" error page
    -- it is not the same identifier space as this site. (Islington Tennis
    Centre outdoor is already polled separately, via the Better Admin API,
    by the existing ``tennis_app`` / GitHub Actions poller.)
  - The table has one row per time slot and one column per rolling day
    (header cells read e.g. "Wed 08"). A cell reads "-" (booked) or
    "N court(s)" (free); free cells additionally carry an "emerald" CSS
    class, which is what this script keys off (more robust than text).

Usage:
    python scripts/highbury_wednesday_watch.py [--state PATH] [--no-notify] [--force]

Verify locally without notifying: add --no-notify. Run twice back-to-back
to exercise the diff path (the second run's cache reflects the first).

Dependencies: requests, beautifulsoup4 (pip install requests beautifulsoup4).
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

URL = "https://localtenniscourts.com/?q=highbury-fields"
DEFAULT_STATE_PATH = os.path.expanduser("~/.cache/highbury_wednesday_watch.json")
CUTOFF_HOUR = 19
WEDNESDAY = 2  # datetime.weekday(): Monday=0 ... Sunday=6

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def fetch_html() -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    r = requests.get(URL, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text


def parse_today_column(html: str, today_label: str) -> dict[str, str]:
    """Return {time_str: cell_text} for the column matching today_label (e.g.
    "Wed 08"), restricted to slots starting at or after CUTOFF_HOUR.

    cell_text is "-" when booked, or the free-slot text (e.g. "1court" /
    "4courts") when free -- callers use ``is_free`` to interpret it.
    """
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    header_table = next((t for t in tables if len(t.select("thead th")) > 1), None)
    data_table = next((t for t in tables if t.select("tbody tr")), None)
    if header_table is None or data_table is None:
        raise RuntimeError("Could not find availability table in page (layout may have changed)")

    headers = [th.get_text(strip=True) for th in header_table.select("thead th")]
    if today_label not in headers:
        raise RuntimeError(f"Today's column ({today_label!r}) not found in page headers: {headers}")
    col_index = headers.index(today_label) - 1  # headers[0] is "Time", not a date column

    slots: dict[str, str] = {}
    for row in data_table.select("tbody tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        time_str = cells[0].get_text(strip=True)
        try:
            hour = int(time_str.split(":")[0])
        except (ValueError, IndexError):
            continue
        if hour < CUTOFF_HOUR:
            continue
        data_cell_index = 1 + col_index
        if data_cell_index >= len(cells):
            continue
        slots[time_str] = cells[data_cell_index].get_text(strip=True)

    return slots


def is_free(cell_text: str) -> bool:
    return cell_text not in ("", "-")


def load_state(path: str) -> dict[str, object]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(path: str, state: dict[str, object]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def newly_freed_slots(prev_slots: dict[str, str], curr_slots: dict[str, str]) -> list[str]:
    return sorted(
        t for t, text in curr_slots.items() if is_free(text) and not is_free(prev_slots.get(t, "-"))
    )


def notify(message: str) -> None:
    title = "Highbury Fields court free!"
    if subprocess.run(["which", "termux-notification"], capture_output=True).returncode == 0:
        subprocess.run(["termux-notification", "--title", title, "--content", message])
        return
    if subprocess.run(["which", "notify-send"], capture_output=True).returncode == 0:
        subprocess.run(["notify-send", title, message])
        return
    if sys.platform == "darwin":
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "{title}"']
        )
        return
    logging.warning(
        "No notification backend found (termux-notification / notify-send / osascript). Message: %s",
        message,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Highbury Fields Wednesday-evening court watch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--state", default=DEFAULT_STATE_PATH, help="Path to state cache file")
    parser.add_argument(
        "--no-notify", action="store_true", help="Skip sending a notification (for testing)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Run even if today isn't Wednesday (for testing)"
    )
    args = parser.parse_args(argv)

    now = datetime.now()
    if now.weekday() != WEDNESDAY and not args.force:
        logging.info("Not Wednesday; nothing to do.")
        return 0

    today_label = now.strftime("%a %d")  # e.g. "Wed 08" -- matches the page's header format

    try:
        html = fetch_html()
        curr = parse_today_column(html, today_label)
    except Exception as e:
        logging.error("fetch/parse failed: %s", e)
        return 1

    cached = load_state(args.state)
    # Only compare against state cached from *today*'s polling session --
    # last Wednesday's snapshot is a different set of dates and would give a
    # meaningless diff.
    raw_slots = cached.get("slots")
    prev: dict[str, str] = (
        raw_slots if isinstance(raw_slots, dict) and cached.get("date") == today_label else {}
    )

    freed = newly_freed_slots(prev, curr)
    if freed:
        details = ", ".join(f"{t} ({curr[t]})" for t in freed)
        message = f"Free from {details} today at Highbury Fields"
        logging.info("ALERT: %s", message)
        if not args.no_notify:
            notify(message)
    else:
        logging.info("Checked %d slot(s) >= %d:00; no new availability.", len(curr), CUTOFF_HOUR)

    save_state(args.state, {"date": today_label, "slots": curr})
    return 0


if __name__ == "__main__":
    sys.exit(main())
