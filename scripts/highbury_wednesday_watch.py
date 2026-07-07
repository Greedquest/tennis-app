#!/usr/bin/env python3
"""Wednesday-evening Highbury Fields court watch.

Standalone, LOCALLY-scheduled monitor (cron / Termux+Tasker) — deliberately
not wired into the GitHub Actions poller or any cloud routine, since routines
run hourly at best and this needs a 5-minute cadence on Wednesday afternoons/
evenings only. Alert only; no booking automation.

Source: https://localtenniscourts.com/?q=highbury-fields
  - No JSON API: the site is a server-rendered Next.js page, and the full
    availability table is already present in a plain HTTP GET (confirmed via
    a throwaway Playwright + requests probe — no browser needed here).
  - Only the "highbury-fields" slug resolves on this site. A second slug for
    Islington Tennis Centre's own outdoor courts ("islington-tennis-centre-
    outdoor") returns an error page there — it is NOT the same identifier
    space as the Better Admin API tennis_app/ already talks to. If ITC
    outdoor coverage is wanted later, it needs its own source/venue slug,
    not this one.

Usage:
    python scripts/highbury_wednesday_watch.py [--state PATH] [--no-notify] [--force]

Verify locally without notifying: add --no-notify. Run twice back-to-back
to see the diff path exercise (the second run's cache reflects the first).
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


def parse_today_column(html: str, today_label: str) -> dict[str, bool]:
    """Return {time_str: is_free} for the date column matching today_label
    (e.g. "Wed 08"), restricted to slots starting at or after CUTOFF_HOUR."""
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

    slots: dict[str, bool] = {}
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
        cell_classes = " ".join(cells[data_cell_index].get("class", []))
        is_free = "emerald" in cell_classes
        slots[time_str] = is_free

    return slots


def load_state(path: str) -> dict[str, bool]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(path: str, state: dict[str, bool]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def newly_freed_slots(prev: dict[str, bool], curr: dict[str, bool]) -> list[str]:
    return sorted(t for t, free in curr.items() if free and not prev.get(t, False))


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
    parser = argparse.ArgumentParser(description="Highbury Fields Wednesday-evening court watch")
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

    today_label = now.strftime("%a %d")  # e.g. "Wed 08" — matches the page's header format

    html = fetch_html()
    curr = parse_today_column(html, today_label)
    prev = load_state(args.state)

    freed = newly_freed_slots(prev, curr)
    if freed:
        message = "Free from " + ", ".join(freed) + " today at Highbury Fields"
        logging.info("ALERT: %s", message)
        if not args.no_notify:
            notify(message)
    else:
        logging.info("Checked %d slot(s) >= %d:00; no new availability.", len(curr), CUTOFF_HOUR)

    save_state(args.state, curr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
