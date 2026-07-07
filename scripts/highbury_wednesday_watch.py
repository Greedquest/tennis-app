#!/usr/bin/env python3
"""Local Wednesday-evening watch for Highbury Fields / Islington Tennis
Centre (outdoor) courts, via localtenniscourts.com.

This is a LOCAL script, not a Claude Code routine or GitHub Actions job:
Claude Code routines run no more often than hourly, but this needs 5-minute
polling on Wednesdays only. Schedule it yourself with cron (or Termux's
crontab / Tasker):

    # crontab -e
    */5 12-21 * * 3 /usr/bin/python3 /path/to/highbury_wednesday_watch.py
    0   22    * * 3 /usr/bin/python3 /path/to/highbury_wednesday_watch.py

(day-of-week 3 = Wednesday; the two lines together cover midday to 22:00.)

How it works:
    localtenniscourts.com/?q=... server-renders a plain HTML table -- no
    JSON API involved. The header row has one column per day ("Wed 08",
    "Thu 09", ...); the second table has one row per time slot, with each
    day's cell reading "-" when fully booked or "N courts" when free. This
    script finds the Wednesday column, reads slots starting at or after
    19:00, and alerts the moment one flips from booked to free.

Dependencies: requests, beautifulsoup4 (pip install requests beautifulsoup4)
"""
import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
DEFAULT_CACHE = Path.home() / ".cache" / "highbury_wednesday_watch.json"
MIN_HOUR = 19  # only alert for slots starting at or after 19:00


def fetch_wednesday_slots() -> dict[str, bool]:
    """Return {"HH:MM": is_available} for the upcoming Wednesday's slots >=19:00."""
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 2:
        raise RuntimeError(f"expected 2 tables (day header + time slots), found {len(tables)}")

    header_cells = tables[0].find_all(["th", "td"])
    day_col = next(
        (i for i, cell in enumerate(header_cells) if re.match(r"^Wed\b", cell.get_text(strip=True))),
        None,
    )
    if day_col is None:
        raise RuntimeError("no Wednesday column in the current rolling week view")

    slots: dict[str, bool] = {}
    for row in tables[1].find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) <= day_col:
            continue
        time_text = cells[0].get_text(strip=True)
        m = re.match(r"^(\d{2}):\d{2}$", time_text)
        if not m or int(m.group(1)) < MIN_HOUR:
            continue
        cell_text = cells[day_col].get_text(strip=True)
        slots[time_text] = cell_text not in ("", "-")
    return slots


def notify(title: str, message: str) -> None:
    if shutil.which("termux-notification"):
        subprocess.run(["termux-notification", "--title", title, "--content", message], check=False)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False)
    elif shutil.which("osascript"):
        subprocess.run(["osascript", "-e", f'display notification "{message}" with title "{title}"'], check=False)
    else:
        logging.warning("No notification backend found (termux-notification/notify-send/osascript).")
        print(f"[ALERT] {title}: {message}")


def load_cache(path: Path) -> dict[str, bool]:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(path: Path, data: dict[str, bool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="Path to the JSON state cache.")
    p.add_argument("--dry-run", action="store_true", help="Log only, don't send a notification.")
    args = p.parse_args(argv)

    try:
        current = fetch_wednesday_slots()
    except Exception as e:
        logging.error("fetch failed: %s", e)
        return 1

    previous = load_cache(args.cache)
    newly_free = sorted(t for t, avail in current.items() if avail and not previous.get(t, False))

    if newly_free:
        msg = "Wednesday slot(s) opened: " + ", ".join(newly_free)
        logging.info(msg)
        if not args.dry_run:
            notify("Tennis court free!", msg)
    else:
        logging.info("Checked %d slot(s) >=19:00, no change.", len(current))

    save_cache(args.cache, current)
    return 0


if __name__ == "__main__":
    sys.exit(main())
