#!/usr/bin/env python3
"""One-off probe: fully parse the SSR table structure - headers (venue/court
columns), slot status classes (booked vs free), and how day/date selection
works (URL param vs client tabs)."""
import re
import sys

import requests
from bs4 import BeautifulSoup

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def main() -> int:
    r = requests.get(URL, headers=HEADERS, timeout=20)
    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table")
    print(f"Found {len(tables)} <table> element(s)")

    for ti, table in enumerate(tables):
        print(f"\n=== TABLE {ti} ===")
        rows = table.find_all("tr")
        print(f"{len(rows)} rows")
        for ri, row in enumerate(rows[:6]):
            cells = row.find_all(["th", "td"])
            cell_summ = []
            for c in cells:
                classes = " ".join(c.get("class", []))
                status = "?"
                if "red" in classes:
                    status = "RED"
                elif "green" in classes:
                    status = "GREEN"
                elif "emerald" in classes:
                    status = "EMERALD"
                text = c.get_text(strip=True)[:20]
                cell_summ.append(f"[{text!r}/{status}]")
            print(f"row {ri}: {' '.join(cell_summ)}")

    # Look for day-of-week selectors / date navigation controls
    print("\n=== DAY/DATE UI SEARCH ===")
    for kw in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "Today", "Tomorrow"]:
        count = len(re.findall(rf"\b{kw}\b", html))
        if count:
            print(f"{kw!r}: {count} occurrence(s)")

    # Check for a date-like query param support by looking at any <a>/<button> href/onclick with date=
    date_params = re.findall(r'date=[0-9\-]+', html)
    print("\ndate= params found in HTML:", sorted(set(date_params))[:10])

    # Dump all distinct classes containing color words to enumerate the full status vocabulary
    color_classes = sorted(set(re.findall(r'\b(?:bg|text)-(?:red|green|emerald|amber|yellow|slate|gray)-\d+[\w/]*', html)))
    print("\nDistinct status-ish classes:", color_classes[:30])

    return 0


if __name__ == "__main__":
    sys.exit(main())
