#!/usr/bin/env python3
"""Throwaway probe: inspect localtenniscourts.com for an underlying JSON API.

Run only where there's real network egress (the sandbox proxy blocks this
host, per CLAUDE.md gotchas) — e.g. as a one-off GitHub Actions job. Fetches
the page HTML and greps for script tags, inline JSON, and any URL-shaped
strings that look like API/data endpoints, so we can tell whether this is a
server-rendered page or a JS app backed by a fetchable JSON API.
"""

import re
import sys

import requests

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

URL_RE = re.compile(r"""["'](https?://[^"']+|/[a-zA-Z0-9_\-/.]*(?:api|json|ajax)[a-zA-Z0-9_\-/.?=&]*)["']""", re.I)
SCRIPT_SRC_RE = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.I)


def main() -> int:
    print(f"GET {URL}")
    r = requests.get(URL, headers=HEADERS, timeout=20)
    print(f"status={r.status_code} content-length={len(r.text)}")
    print(f"content-type={r.headers.get('content-type')}")

    html = r.text

    print("\n--- <script src=...> tags ---")
    for m in sorted(set(SCRIPT_SRC_RE.findall(html))):
        print(m)

    print("\n--- candidate API/JSON-looking URLs found anywhere in HTML ---")
    for m in sorted(set(URL_RE.findall(html))):
        print(m)

    print("\n--- lines mentioning 'fetch(' or 'XMLHttpRequest' or 'axios' ---")
    for line in html.splitlines():
        if any(tok in line for tok in ("fetch(", "XMLHttpRequest", "axios", "api/", ".json")):
            print(line.strip()[:300])

    print("\n--- first 3000 chars of body (to check server-rendered vs SPA shell) ---")
    print(html[:3000])

    print("\n--- last 2000 chars of body ---")
    print(html[-2000:])

    return 0


if __name__ == "__main__":
    sys.exit(main())
