#!/usr/bin/env python3
"""Probe https://localtenniscourts.com's raw HTML for embedded availability data.

Throwaway diagnostic: the sandbox that authors this repo's code can't reach
localtenniscourts.com directly (proxy 403s it), so this script is meant to be
run somewhere with real network egress (a GitHub Actions job) so its output
can be read back as logs. Not wired into the app — delete once the site's
data shape is understood.

Playwright network capture showed the rendered page has a full data table
(times x days x court counts) despite ZERO xhr/fetch calls for it - and the
plain-requests fetch of the page was ~86KB, far too large for an empty SPA
shell. That strongly suggests the table markup is already present in the
raw server response (edge-rendered per the ?q= param), not fetched
client-side. This probe fetches the raw HTML with plain `requests` (no
browser) and checks whether the time/day/court-count table is present as
literal HTML - if so, the whole app can be built with `requests` alone.
"""

import re
import sys

import requests

PAGE_URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def main() -> int:
    r = requests.get(PAGE_URL, headers=HEADERS, timeout=20)
    text = r.text
    print(f"status={r.status_code} bytes={len(r.content)} chars={len(text)}")

    for needle in ("08:00", "19:00", "court", "Highbury", "Islington", "Thu", "Wed"):
        count = text.count(needle)
        print(f"occurrences of {needle!r}: {count}")

    idx = text.find("08:00")
    print(f"\n--- context around first '08:00' occurrence (idx={idx}) ---")
    if idx != -1:
        print(text[max(0, idx - 1500) : idx + 3000])
    else:
        print("(not found in raw HTML - data likely IS client-rendered only)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
