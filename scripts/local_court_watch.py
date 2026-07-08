#!/usr/bin/env python3
"""
Local Wednesday-evening court-availability monitor for localtenniscourts.com.

Polls the combined Highbury Fields / Islington Tennis Centre (outdoor) search
page and desktop-notifies the moment a slot starting at or after 19:00 on
Wednesday flips from booked to free. Alert only -- no booking automation.

This is deliberately a standalone local script, not a Claude Code cloud
routine: cloud routines run hourly at best, and this needs a 5-minute
cadence during a narrow window. Schedule it yourself with cron or Termux:

    # Every 5 minutes, Wednesdays only, midday to 22:00
    */5 12-21 * * 3 cd /path/to/tennis-app && .venv/bin/python scripts/local_court_watch.py

localtenniscourts.com has no JSON API: the availability grid is fully
server-rendered into the initial HTML response, so a plain GET + HTML parse
is the only (and simplest) approach -- confirmed by inspecting the page with
a real browser and finding zero XHR/fetch calls beyond analytics beacons.

State (the last-seen availability count per Wednesday time slot) is cached
at ~/.cache/tennis-watch/state.json so only *new* availability triggers an
alert, not every still-free slot on every run.
"""

import argparse
import json
import logging
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"
MIN_HOUR = 19  # only alert on slots starting at/after 19:00
DEFAULT_STATE_FILE = Path.home() / ".cache" / "tennis-watch" / "state.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def parse_wednesday_slots(html: str) -> dict[str, int]:
    """
    Parse the availability grid and return {"HH:MM": available_court_count}
    for the Wednesday column, restricted to times >= MIN_HOUR.
    """
    soup = BeautifulSoup(html, "html.parser")

    # The header and body are rendered as two separate <table> elements
    # (a sticky-header layout trick), so gather thead/tbody across all of them.
    headers = [th.get_text(strip=True) for th in soup.select("thead th")]
    if not headers:
        raise RuntimeError("No table header found on page -- site markup may have changed")

    wed_col = next(
        (i for i, h in enumerate(headers) if re.match(r"Wed \d{1,2}", h)),
        None,
    )
    if wed_col is None:
        logging.info("No Wednesday column in the current window; nothing to check.")
        return {}

    slots: dict[str, int] = {}
    for row in soup.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) <= wed_col:
            continue
        time_str = cells[0].get_text(strip=True)
        m = re.match(r"(\d{1,2}):\d{2}", time_str)
        if not m or int(m.group(1)) < MIN_HOUR:
            continue
        count_span = cells[wed_col].select_one("span.font-semibold")
        text = count_span.get_text(strip=True) if count_span else "-"
        slots[time_str] = 0 if text == "-" else int(text)

    return slots


def fetch_wednesday_slots(url: str = URL) -> dict[str, int]:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return parse_wednesday_slots(r.text)


def load_state(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(path: Path, state: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state))


def find_newly_free(prev: dict[str, int], curr: dict[str, int]) -> list[str]:
    """Times where availability went from 0 (or unseen) to >0 courts."""
    return sorted(t for t, count in curr.items() if count > 0 and prev.get(t, 0) == 0)


def notify(message: str) -> None:
    """Best-effort desktop notification across Termux / macOS / Linux."""
    title = "Tennis court free!"
    if shutil.which("termux-notification"):
        subprocess.run(
            ["termux-notification", "--title", title, "--content", message], check=False
        )
    elif platform.system() == "Darwin" and shutil.which("osascript"):
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False)
    else:
        logging.warning("No desktop notifier found (tried termux-notification/osascript/notify-send)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--url", default=URL)
    parser.add_argument(
        "--html-file", type=Path, help="Parse a saved HTML file instead of fetching (for testing)"
    )
    parser.add_argument("--no-notify", action="store_true", help="Log only, skip the notification")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.html_file:
        curr = parse_wednesday_slots(args.html_file.read_text())
    else:
        curr = fetch_wednesday_slots(args.url)

    prev = load_state(args.state_file)
    newly_free = find_newly_free(prev, curr)

    if newly_free:
        message = "\n".join(f"{t} - {curr[t]} court(s) free" for t in newly_free)
        logging.info("ALERT:\n%s", message)
        if not args.no_notify:
            notify(message)
    else:
        logging.info(
            "Checked %d Wednesday slot(s) >= %02d:00; no new availability.", len(curr), MIN_HOUR
        )

    save_state(args.state_file, curr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
