#!/usr/bin/env python3
"""Throwaway probe, round 2: inspect the localtenniscourts.com JS bundles.

Round 1 (Playwright, full page load) captured every network response and
found NO XHR/fetch call carrying court data — only the HTML shell, two JS
bundles, a CSS file, and third-party analytics/widget requests. That means
either the data is baked into the JS bundle at build time, or it's fetched
by some code path this quick page-load probe didn't trigger. This round
downloads the two bundle files directly (plain HTTPS GET, no browser needed)
and greps them for anything API/data-shaped: fetch(...) calls, request-y
URLs, and known keywords from our own better-admin/bookings integration.
"""

import re
import sys

import requests

BASE = "https://localtenniscourts.com"
ASSETS = [
    "/assets/index-Bf7utVcV.js",
    "/assets/main-DLXMVjOc.js",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

URL_RE = re.compile(r"""https?://[^\s"'`)]+""")
KEYWORDS = [
    "better-admin",
    "bookings.better",
    "better.org.uk",
    "fetch(",
    "XMLHttpRequest",
    "axios",
    "/api/",
    ".json",
    "highbury",
    "islington",
    "availability",
    "spaces",
]


def main() -> int:
    for path in ASSETS:
        url = BASE + path
        print(f"\n=== GET {url} ===")
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"status={r.status_code} length={len(r.text)}")
        text = r.text

        print("--- unique http(s) URLs referenced ---")
        for u in sorted(set(URL_RE.findall(text))):
            print(u)

        print("--- keyword hits (keyword: count) ---")
        for kw in KEYWORDS:
            count = text.count(kw)
            if count:
                print(f"{kw}: {count}")
                # show first occurrence with context
                idx = text.find(kw)
                start = max(0, idx - 150)
                end = min(len(text), idx + 150)
                print(f"    context: ...{text[start:end]}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
