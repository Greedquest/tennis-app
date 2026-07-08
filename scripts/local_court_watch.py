#!/usr/bin/env python3
"""Local Wednesday-evening court watch: alert when a >=19:00 slot opens up.

Not part of the ``tennis_app`` GitHub Actions poller — that package watches a
different source (the Better Admin API directly) on a different schedule for
a different routine. This script is a standalone, dependency-light monitor
for https://localtenniscourts.com, meant to be run by a *local* scheduler
(cron / Termux+Tasker) every 5 minutes, Wednesdays only, since Claude Code
routines are hourly-minimum and can't hit a 5-minute cadence.

Data source
-----------
localtenniscourts.com aggregates several London booking systems (itself
scraping, among others, the same better-admin.org.uk backend this repo's
other poller talks to) and re-serves them through a TanStack Start app. There
is no plain JSON API: the page embeds its loader data directly in the HTML
as a "seroval" reference-graph script (``$R[n]=...``), not a `<script
type="application/json">` blob. ``_extract_table_data`` below turns that
back into a normal dict by stripping the ``$R[n]=`` assignment prefixes
(safe here because nothing in this subtree is a shared/aliased reference)
and quoting bare object keys, then parsing what's left as JSON.

Verify locally without hitting the network (the sandbox this was developed
in has its egress blocked for this domain; confirmed live via a throwaway
GitHub Actions probe instead — see scripts/probe_localtenniscourts.py):

    python scripts/local_court_watch.py --fixture testing/fixtures/localtenniscourts_sample.html \
        --cache /tmp/local_court_watch_state.json --dry-run --force

Run twice with the same --cache to exercise the diff path.

Example crontab entry (Wednesdays, noon-22:00, every 5 minutes; the script
re-checks the day/time itself, so a coarser cron schedule is also safe):

    */5 12-21 * * 3 cd /path/to/tennis-app && python3 scripts/local_court_watch.py
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from typing import Any

import requests

SOURCE_URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Discovered by probing the site's embedded loader data for this exact query
# (see scripts/probe_localtenniscourts.py); re-probe if these ever stop
# matching the names returned in each slot's "spaces" entries.
TARGET_VENUES = {
    1: "Highbury Fields",
    5: "Islington Tennis Centre - Outdoor",
}

MIN_HOUR = 19  # only alert on slots starting at or after 19:00
DEFAULT_CACHE_PATH = "cache/local_court_watch_state.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("local_court_watch")


def _extract_balanced(s: str, start: int) -> str:
    """Return the balanced {...} or [...] substring of ``s`` starting at ``start``."""
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(s)):
        c = s[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c in "{[":
                depth += 1
            elif c in "}]":
                depth -= 1
                if depth == 0:
                    return s[start : j + 1]
    raise ValueError("unbalanced brackets while scanning embedded page data")


def extract_table_data(page_html: str) -> dict[str, Any]:
    """Pull the ``tableData`` loader value out of the page's embedded seroval payload."""
    m = re.search(r"l:\$R\[\d+\]=\{tableData:", page_html)
    if not m:
        raise ValueError("Could not find tableData in page — site markup may have changed")

    i = m.end()
    ref_prefix = re.match(r"\$R\[\d+\]=", page_html[i:])
    if ref_prefix:
        i += ref_prefix.end()

    raw = _extract_balanced(page_html, i)
    cleaned = re.sub(r"\$R\[\d+\]=", "", raw)
    cleaned = re.sub(r"([{,])([A-Za-z_$][A-Za-z0-9_$]*):", r'\1"\2":', cleaned)
    return json.loads(cleaned)


def fetch_page(fixture_path: str | None) -> str:
    if fixture_path:
        log.info("Loading page from fixture file: %s", fixture_path)
        with open(fixture_path, encoding="utf-8") as f:
            return f.read()

    log.info("Fetching %s", SOURCE_URL)
    r = requests.get(SOURCE_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def find_wednesday_field(columns: list[dict[str, str]]) -> str | None:
    for col in columns:
        if col["title"].startswith("Wed"):
            return col["field"]
    return None


def collect_wednesday_evening_slots(table_data: dict[str, Any]) -> dict[str, int]:
    """Return {"<date>|<time>|<venue_id>": total_spaces} for Wed rows with hour >= MIN_HOUR."""
    field = find_wednesday_field(table_data["columns"])
    if field is None:
        return {}

    today = datetime.now().date().isoformat()
    slots: dict[str, int] = {}
    for row in table_data["rows"]:
        if row["hour"] < MIN_HOUR:
            continue
        cell = row.get(field)
        if not cell:
            continue
        for space in cell.get("spaces", []):
            venue_id = space.get("venue_id")
            if venue_id not in TARGET_VENUES:
                continue
            key = f"{today}|{row['fromTime']}|{venue_id}"
            slots[key] = space.get("total_spaces", 0)
    return slots


def load_prev_state(path: str) -> dict[str, int]:
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


def diff_freed_slots(prev: dict[str, int], curr: dict[str, int]) -> list[str]:
    """Keys that went from 0 spaces to >0 spaces (booked -> free)."""
    return [k for k, spaces in curr.items() if spaces > 0 and prev.get(k) == 0]


def describe_slot(key: str, spaces: int) -> str:
    date, time, venue_id_str = key.split("|")
    venue_id = int(venue_id_str)
    venue_name = TARGET_VENUES.get(venue_id, venue_id_str)
    return f"{venue_name} {date} {time}: {spaces} space(s) free"


def send_desktop_notification(title: str, message: str) -> bool:
    """Best-effort desktop notification across Termux, Linux, and macOS."""
    if shutil.which("termux-notification"):
        subprocess.run(
            ["termux-notification", "--title", title, "--content", message], check=False
        )
        return True
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False)
        return True
    if shutil.which("osascript"):
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False)
        return True
    return False


def in_watch_window(now: datetime) -> bool:
    return now.weekday() == 2 and 12 <= now.hour < 22  # Monday=0 -> Wednesday=2


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Local Wednesday-evening tennis court watch")
    p.add_argument("--cache", default=DEFAULT_CACHE_PATH, help="Path to the state cache file")
    p.add_argument(
        "--fixture", default=None, help="Read a saved HTML page instead of hitting the network"
    )
    p.add_argument(
        "--force", action="store_true", help="Run even outside the Wed noon-22:00 window"
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Log what would be alerted, skip the notification"
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    now = datetime.now()

    if not args.force and not in_watch_window(now):
        log.info("Outside the Wednesday noon-22:00 watch window; skipping.")
        return 0

    try:
        page_html = fetch_page(args.fixture)
        table_data = extract_table_data(page_html)
    except Exception:
        log.exception("Fetch/parse failed")
        return 1

    curr = collect_wednesday_evening_slots(table_data)
    if not curr:
        log.info("No Wednesday >=19:00 data in range (likely past today's booking cutoff).")
        return 0

    prev = load_prev_state(args.cache)
    freed = diff_freed_slots(prev, curr)

    if freed:
        lines = [describe_slot(k, curr[k]) for k in freed]
        message = "\n".join(lines)
        log.info("Slot(s) opened up:\n%s", message)
        if args.dry_run:
            log.info("Dry run: notification not sent.")
        else:
            sent = send_desktop_notification("Tennis court available!", message)
            if not sent:
                log.warning(
                    "No notifier found (termux-notification / notify-send / osascript); "
                    "logging only:\n%s",
                    message,
                )
    else:
        log.info("Checked %d Wednesday evening slot(s); no change.", len(curr))

    save_state(args.cache, curr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
