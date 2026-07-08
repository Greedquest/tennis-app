#!/usr/bin/env python3
"""Wednesday-evening tennis court watch: local scheduled monitor.

Polls https://localtenniscourts.com for combined Highbury Fields / Islington
Tennis Centre (outdoor) availability and fires a desktop notification the
moment a Wednesday slot starting at or after 19:00 flips from booked to free.
Alert only -- no booking automation, Mr Hall books manually.

Why this is a separate, local script and not part of the cloud GitHub Actions
poller in `tennis_app/`:
  - localtenniscourts.com has no JSON API. The whole availability table --
    including per-slot counts -- is server-rendered into the initial HTML
    response (confirmed by probing from a GitHub Actions runner with real
    network egress: a plain `requests.get` already returns a full <tbody>
    with slot data, no browser/XHR needed). So this is a straightforward
    HTML parse, not a scrape-as-last-resort situation.
  - The alert channel is a desktop notification, which only makes sense
    running on a machine with a session to notify -- not from a cloud job.
  - The required cadence (every 5 minutes, Wednesdays only, midday-22:00) is
    finer-grained than Claude Code cloud routines support (hourly minimum),
    so this is meant to be invoked by local cron / Tasker (per the existing
    Termux setup) or run as a long-lived loop -- not deployed to CI.

The query page combines both venues into one column per day (one number =
availability across Highbury Fields + Islington Tennis Centre outdoor
combined), so no per-venue split is needed here.

Scheduling (crontab -e), Wednesdays every 5 minutes from noon to 22:00:
    */5 12-21 * * 3 /usr/bin/python3 /path/to/scripts/wednesday_watch.py

(Hour range 12-21 covers checks through 21:55; a single extra 22:00 tick
isn't worth a second cron line for a soft cutoff.)

Usage:
    python scripts/wednesday_watch.py [--cache PATH] [--no-notify] [--html-fixture PATH]
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import time as dt_time

import requests

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"
DEFAULT_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "cache", "wednesday_watch_state.json"
)
MIN_START_TIME = dt_time(19, 0)  # only alert for slots starting >= 19:00

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

TABLE_RE = re.compile(r"<table[^>]*>.*?</table>", re.DOTALL)
TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
TH_RE = re.compile(r"<th[^>]*>(.*?)</th>", re.DOTALL)
SPAN_TEXT_RE = re.compile(r"<span[^>]*>([^<]*)</span>")
TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(html: str) -> str:
    return TAG_RE.sub("", html).strip()


def fetch_html(url: str = URL) -> str:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def parse_slots(html: str) -> list[dict]:
    """
    Parse the rendered availability table into a flat list of slot dicts:
        {"weekday": "Wed", "day": "08", "time": "19:00", "spaces": 0}

    The page renders two <table> elements: a sticky header (day columns,
    no <tbody>) and a data table with <tbody> rows (one per time slot).
    """
    tables = TABLE_RE.findall(html)
    header_table = next((t for t in tables if "<tbody" not in t), None)
    data_table = next((t for t in tables if "<tbody" in t), None)
    if not header_table or not data_table:
        raise ValueError("Could not locate availability table in page HTML")

    headers = [_strip_tags(h) for h in TH_RE.findall(header_table)]
    day_columns = headers[1:]  # drop the leading "Time" column

    slots: list[dict] = []
    for row_html in TR_RE.findall(data_table):
        cells = TD_RE.findall(row_html)
        if len(cells) != len(day_columns) + 1:
            continue  # unexpected row shape; skip defensively
        time_str = _strip_tags(cells[0])
        for day_header, cell_html in zip(day_columns, cells[1:]):
            weekday, _, day_num = day_header.partition(" ")
            span_text = SPAN_TEXT_RE.findall(cell_html)
            count_text = span_text[0] if span_text else "-"
            spaces = 0 if count_text == "-" else int(count_text)
            slots.append({"weekday": weekday, "day": day_num, "time": time_str, "spaces": spaces})
    return slots


def wednesday_evening_slots(slots: list[dict]) -> dict[str, int]:
    """Filter to Wednesday slots starting >= 19:00, keyed by "day|time"."""
    result = {}
    for slot in slots:
        if slot["weekday"] != "Wed":
            continue
        hour, _, minute = slot["time"].partition(":")
        try:
            slot_time = dt_time(int(hour), int(minute))
        except ValueError:
            continue
        if slot_time < MIN_START_TIME:
            continue
        result[f"{slot['day']}|{slot['time']}"] = slot["spaces"]
    return result


def load_prev(cache_path: str) -> dict[str, int]:
    try:
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_curr(cache_path: str, curr: dict[str, int]) -> None:
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    tmp = cache_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(curr, f)
    os.replace(tmp, cache_path)


def find_newly_free(prev: dict[str, int], curr: dict[str, int]) -> list[str]:
    """Keys where spaces went from 0 (or unseen, treated as booked) to >0."""
    return [key for key, spaces in curr.items() if spaces > 0 and prev.get(key, 0) == 0]


def notify(title: str, message: str) -> None:
    """Best-effort desktop notification across common local setups."""
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
    # No known notifier on this machine -- print loudly so a foreground
    # terminal or log tail at least surfaces it.
    print(f"\a*** {title} ***\n{message}", flush=True)


def check_once(cache_path: str, do_notify: bool, html: str | None = None) -> int:
    if html is None:
        html = fetch_html()
    slots = parse_slots(html)
    curr = wednesday_evening_slots(slots)
    prev = load_prev(cache_path)

    newly_free = find_newly_free(prev, curr)
    if newly_free:
        lines = [
            f"  {key.replace('|', ' at ')}: {curr[key]} court(s)" for key in sorted(newly_free)
        ]
        message = "Wednesday evening slot(s) opened up:\n" + "\n".join(lines)
        logging.info(message)
        if do_notify:
            notify("Tennis court free!", message)
    else:
        logging.info("Checked %d Wednesday >=19:00 slot(s); no change.", len(curr))

    save_curr(cache_path, curr)
    return len(newly_free)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wednesday-evening tennis court watch")
    parser.add_argument("--cache", default=DEFAULT_CACHE_PATH, help="Path to the cache JSON file")
    parser.add_argument("--no-notify", action="store_true", help="Log only, skip notification")
    parser.add_argument(
        "--html-fixture",
        default=None,
        help="Path to a saved HTML file to parse instead of fetching the live page (testing)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    html = None
    if args.html_fixture:
        with open(args.html_fixture, encoding="utf-8") as f:
            html = f.read()

    check_once(args.cache, do_notify=not args.no_notify, html=html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
