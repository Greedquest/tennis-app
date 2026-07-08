#!/usr/bin/env python3
"""Local Wednesday-evening court watcher for localtenniscourts.com.

Standalone script — separate from the ``tennis_app`` package, which polls a
different site (Better Admin / islington-tennis-centre via GitHub Actions,
see CLAUDE.md). This one targets:

    https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor

which is itself an aggregator combining Highbury Fields and Islington Tennis
Centre (outdoor) into one table, so "a court opened up" is deliberately not
attributed to a single venue.

The page is server-rendered: a plain ``requests.get()`` already returns the
full availability table, no browser/JS needed (confirmed by probing from a
GitHub Actions runner, since this project's sandbox can't reach the domain).

Meant to be invoked by cron (or Termux/Tasker) every 5 minutes, Wednesdays
only, ~midday-22:00 — the schedule itself provides the "Wednesday, working
hours" narrowing; this script just does one fetch-diff-alert pass per run.
Alert only, no booking automation.

Usage:
    python scripts/watch_wednesday_ltc.py [--cache PATH] [--no-notify]

Verify without a real cron, using a saved fixture:
    python scripts/watch_wednesday_ltc.py --fixture testing/fixtures/localtenniscourts_sample.html \\
        --cache /tmp/ltc_state.json --no-notify
    # run twice; the second run diffs against the first (no-op on identical input)

Crontab (every 5 min, Wednesdays, 12:00-22:00 local time):
    */5 12-21 * * 3 cd /path/to/tennis-app && python3 scripts/watch_wednesday_ltc.py
    0   22    * * 3 cd /path/to/tennis-app && python3 scripts/watch_wednesday_ltc.py

Termux: same command via `crontab -e` under termux-services, or a Tasker
profile (time range Wed 12:00-22:00, interval 5 min) running a Termux:Boot
shell task that shells out to it.

Known fragility: this parses the site's current React/Tailwind markup
(class names like "bg-emerald-100" for free, "bg-red-100/50" for booked).
If the site redesigns, re-probe it (see .github/workflows — probe workflows
are throwaway, not kept in the repo) and update parse_slots() accordingly.
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys

import requests

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_CACHE = os.path.join(os.path.dirname(__file__), "..", "cache", "ltc_wednesday_state.json")
MIN_TIME = "19:00"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def fetch_html() -> str:
    r = requests.get(URL, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return r.text


def parse_slots(html: str) -> dict[str, dict]:
    """Parse the availability table into ``{"<day header>|<time>": {...}}``.

    Keyed on the table's own "Day DD" header text (e.g. "Wed 08") plus the
    time label, so a stale cache entry naturally ages out once the site's
    rolling date window moves past it, rather than comparing across weeks.
    """
    thead_match = re.search(r"<thead.*?</thead>", html, re.DOTALL)
    if not thead_match:
        raise ValueError("Could not find table header - page structure may have changed")
    day_headers = re.findall(r'<th data-slot="table-head"[^>]*>([^<]+)</th>', thead_match.group(0))
    if not day_headers or day_headers[0] != "Time":
        raise ValueError(f"Unexpected table header: {day_headers!r}")
    day_headers = day_headers[1:]  # drop the leading "Time" column

    slots: dict[str, dict] = {}
    for row_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL):
        row_html = row_match.group(1)
        time_match = re.search(r'sticky left-0 z-10">([^<]+)</td>', row_html)
        if not time_match:
            continue  # header row or something else, not a time row
        time_label = time_match.group(1)

        # First cell is the sticky time label itself (matches the same
        # pattern); everything after it lines up with day_headers.
        cells = re.findall(
            r'<td data-slot="table-cell" class="([^"]*)">(.*?)</td>', row_html, re.DOTALL
        )
        for day_header, (cell_class, cell_body) in zip(day_headers, cells[1:], strict=False):
            is_free = "emerald" in cell_class
            courts = None
            if is_free:
                n = re.search(r'font-semibold">(\d+)<', cell_body)
                courts = int(n.group(1)) if n else None
            key = f"{day_header}|{time_label}"
            slots[key] = {
                "day": day_header,
                "time": time_label,
                "free": is_free,
                "courts": courts,
            }
    return slots


def wednesday_evening_slots(slots: dict[str, dict]) -> dict[str, dict]:
    return {k: v for k, v in slots.items() if v["day"].startswith("Wed") and v["time"] >= MIN_TIME}


def load_cache(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_cache(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def notify_desktop(title: str, message: str) -> None:
    """Fire a desktop notification, trying Termux, then Linux, then macOS."""
    if shutil.which("termux-notification"):
        subprocess.run(["termux-notification", "--title", title, "--content", message], check=False)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False)
    elif shutil.which("osascript"):
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False)
    else:
        logging.warning(
            "No desktop notifier found (tried termux-notification/notify-send/osascript). "
            "ALERT: %s - %s",
            title,
            message,
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Watch localtenniscourts.com for Wednesday >=19:00 openings."
    )
    p.add_argument(
        "--cache", default=DEFAULT_CACHE, help=f"Path to state cache (default: {DEFAULT_CACHE})"
    )
    p.add_argument(
        "--no-notify", action="store_true", help="Disable desktop notification (for testing)"
    )
    p.add_argument(
        "--fixture", help="Path to a saved HTML file to parse instead of fetching live (testing)"
    )
    args = p.parse_args(argv)

    if args.fixture:
        logging.info("Loading HTML from fixture file: %s", args.fixture)
        with open(args.fixture, encoding="utf-8") as f:
            html = f.read()
    else:
        html = fetch_html()

    all_slots = parse_slots(html)
    tracked = wednesday_evening_slots(all_slots)
    logging.info("Checked %d Wednesday >=19:00 slot(s)", len(tracked))

    prev = load_cache(args.cache)

    newly_free = []
    for key, slot in tracked.items():
        was_free = prev.get(key, {}).get("free", False)
        if slot["free"] and not was_free:
            newly_free.append(slot)

    if newly_free:
        message = "\n".join(f"{s['day']} {s['time']} - {s['courts']} court(s)" for s in newly_free)
        logging.info("OPENED UP:\n%s", message)
        if not args.no_notify:
            notify_desktop("Tennis court free!", message)
    else:
        logging.info("No newly-opened Wednesday evening slots.")

    save_cache(args.cache, tracked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
