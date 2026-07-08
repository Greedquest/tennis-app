#!/usr/bin/env python3
"""Throwaway probe v4: is the availability table server-rendered (no JS needed)?

v3 showed table rows with real availability data appear ~1s after load, but
no XHR/fetch/websocket request was ever observed besides the single GET for
the page itself. That points to server-side rendering: the initial HTML
response already contains the filled-in table, and the JS bundle just
hydrates it (no client-side data fetch).

This probe does a plain ``requests.get`` (no browser at all) and checks
whether the raw response body already contains the table with real slot
counts. If so, production polling can be a simple HTTP GET + HTML parse,
no Playwright/browser dependency needed.

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
    print(f"Status: {r.status_code}", file=sys.stderr)
    html = r.text
    print(f"Raw HTML length: {len(html)}")

    print("\n--- has <tbody> ---")
    print("<tbody" in html)

    print("\n--- has 'Wed 08' header text ---")
    print("Wed 08" in html)

    print("\n--- count of 'court' occurrences ---")
    print(html.count("court"))

    # Try to locate the table and print it verbatim
    m = re.search(r"<table.*?</table>", html, re.DOTALL)
    print("\n--- TABLE MATCH FOUND ---")
    print(bool(m))
    if m:
        print("\n--- TABLE HTML (verbatim from raw response) ---")
        print(m.group(0))

    # Also check for any inline JSON-looking payload (e.g. __DATA__, window.__)
    print("\n--- inline script data markers ---")
    for marker in ("__DATA__", "window.__", "application/json", "self.__next_f"):
        print(marker, "->", marker in html)

    return 0


if __name__ == "__main__":
    sys.exit(main())
