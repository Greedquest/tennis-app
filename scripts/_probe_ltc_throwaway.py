#!/usr/bin/env python3
"""One-off probe: inspect localtenniscourts.com for an underlying JSON API."""
import json
import re
import sys

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"


def main() -> int:
    r = requests.get(URL, headers=HEADERS, timeout=20)
    print(f"STATUS: {r.status_code}")
    print(f"LEN: {len(r.text)}")
    html = r.text

    # 1. Look for embedded JSON blobs (Next.js, Nuxt, etc.)
    for marker in ["__NEXT_DATA__", "__NUXT__", "window.__INITIAL_STATE__", "application/json"]:
        if marker in html:
            print(f"FOUND MARKER: {marker}")

    # 2. Find script src references
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
    print("\n--- SCRIPT SRCS ---")
    for s in scripts:
        print(s)

    # 3. Find any /api/ or json-looking paths mentioned in the HTML
    api_like = sorted(set(re.findall(r'["\'](/[a-zA-Z0-9_\-./]*api[a-zA-Z0-9_\-./]*)["\']', html)))
    print("\n--- API-LIKE PATHS IN HTML ---")
    for a in api_like:
        print(a)

    # 4. Dump a snippet of raw HTML for manual inspection (first 3000 chars)
    print("\n--- HTML HEAD SNIPPET ---")
    print(html[:3000])

    # 5. Try fetching same-origin scripts and grep them for fetch()/axios/api endpoints
    print("\n--- SCANNING JS BUNDLES FOR ENDPOINTS ---")
    base = "https://localtenniscourts.com"
    for s in scripts[:8]:
        src = s if s.startswith("http") else (base + s if s.startswith("/") else f"{base}/{s}")
        try:
            jr = requests.get(src, headers=HEADERS, timeout=20)
            endpoints = sorted(set(re.findall(r'["\'`](https?://[a-zA-Z0-9_\-./]*(?:api|json)[a-zA-Z0-9_\-./]*)["\'`]', jr.text)))
            rel_endpoints = sorted(set(re.findall(r'["\'`](/(?:api|graphql)[a-zA-Z0-9_\-./]*)["\'`]', jr.text)))
            if endpoints or rel_endpoints:
                print(f"\n{src} ({len(jr.text)} bytes):")
                for e in endpoints + rel_endpoints:
                    print(" ", e)
        except Exception as e:
            print(f"  ERR fetching {src}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
