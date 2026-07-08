#!/usr/bin/env python3
"""THROWAWAY probe: inspect localtenniscourts.com table structure.

Not part of the app. Confirmed SSR (plain requests.get returns the full
populated table, no JS/XHR needed). This pass extracts the >=19:00 rows and
looks for what a free (non "-") cell's markup looks like. Delete after use.
"""

import re

import requests

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def main() -> int:
    r = requests.get(URL, headers={"User-Agent": UA}, timeout=20)
    html = r.text
    print(f"status={r.status_code} len={len(html)}")

    # Distinct background classes used across all cells -> status vocabulary
    print("\n=== distinct td class attrs (status vocabulary) ===")
    classes = set(re.findall(r'<td data-slot="table-cell" class="([^"]+)"', html))
    for c in sorted(classes):
        print(repr(c))

    # Pull out each row: header cell (time) + all td cell inner content/classes
    print("\n=== rows from 18:00 to 21:00 ===")
    row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
    for row_match in row_pattern.finditer(html):
        row_html = row_match.group(1)
        time_match = re.search(r'sticky left-0 z-10">([^<]+)</td>', row_html)
        if not time_match:
            continue
        label = time_match.group(1)
        if label not in ("18:00", "19:00", "19:30", "20:00", "21:00"):
            continue
        print(f"\n--- row {label} ---")
        print(row_html[:6000])

    # Table header row (day columns) so we can map column index -> date
    print("\n=== header row (day columns) ===")
    thead_match = re.search(r"<thead.*?</thead>", html, re.DOTALL)
    if thead_match:
        print(thead_match.group(0))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
