#!/usr/bin/env python3
"""Throwaway probe v5: confirmed SSR (raw GET has full table+tbody).

v4 confirmed the raw, un-rendered HTML response already contains
``<tbody>`` and slot-count data ("court"/"courts" occurs 33 times) --
this table is server-rendered, no browser/XHR needed for production polling.

v4's naive non-greedy ``<table>.*?</table>`` regex only matched a *separate*
header-only <table> (sticky header pattern), missing the real data table.
This probe finds every top-level <table>...</table> block and dumps the one
containing <tbody>, plus a couple of raw <tr> rows, so we can write an
accurate parser.

Usage: python scripts/probe_ltc.py
"""

import re
import sys

import requests

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"


def main() -> int:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }
    r = requests.get(URL, headers=headers, timeout=20)
    html = r.text
    print(f"Status: {r.status_code}, length: {len(html)}", file=sys.stderr)

    tables = re.findall(r"<table[^>]*>.*?</table>", html, re.DOTALL)
    print(f"\n--- NUMBER OF <table> BLOCKS: {len(tables)} ---")
    for i, t in enumerate(tables):
        print(f"table[{i}] length={len(t)} has_tbody={'<tbody' in t}")

    data_table = next((t for t in tables if "<tbody" in t), None)
    print("\n--- DATA TABLE (the one with <tbody>) ---")
    print(data_table)

    if data_table:
        rows = re.findall(r"<tr[^>]*>.*?</tr>", data_table, re.DOTALL)
        print(f"\n--- NUMBER OF <tr> IN DATA TABLE: {len(rows)} ---")
        print("\n--- FIRST 3 ROWS ---")
        for row in rows[:3]:
            print(row)
        print("\n--- A ROW CONTAINING 'court' (if any) ---")
        for row in rows:
            if "court" in row:
                print(row)
                break

    return 0


if __name__ == "__main__":
    sys.exit(main())
