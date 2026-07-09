#!/usr/bin/env python3
"""Throwaway probe: check if localtenniscourts.com renders court data server-side.

Not meant to be kept in the repo -- run once on a GitHub Actions runner (real
egress), read the logs, then delete this file + its workflow.
"""

import re
import sys

import requests

BASE = "https://localtenniscourts.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

URLS = [
    f"{BASE}/?q=highbury-fields%2Cislington-tennis-centre-outdoor",
    f"{BASE}/",
]

KEYWORDS = [
    "Highbury",
    "Islington",
    "Clissold",
    "Regent",
    "Finsbury",
    "Hackney",
    "court",
    "Court",
    "available",
    "Available",
    "booked",
    "Booked",
    ":00",
    ":30",
    "spaces",
    "Spaces",
    "<table",
    "<tr",
    "<td",
    "wednesday",
    "Wednesday",
]


def main() -> int:
    for url in URLS:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"\n=== {url} ===")
        print("status:", r.status_code, "len:", len(r.content))
        body = r.text

        for kw in KEYWORDS:
            n = body.count(kw)
            print(f"  count({kw!r}) = {n}")

        # Print a chunk from the middle and end of the body -- the head/meta
        # tags dominate the first ~3000 chars, so look further in.
        mid = len(body) // 2
        print("\n--- body[3000:6000] ---")
        print(body[3000:6000])
        print(f"\n--- body[{mid}:{mid + 3000}] ---")
        print(body[mid : mid + 3000])
        print("\n--- last 2000 chars ---")
        print(body[-2000:])

    return 0


if __name__ == "__main__":
    sys.exit(main())
