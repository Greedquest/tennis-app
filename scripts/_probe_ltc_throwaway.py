#!/usr/bin/env python3
"""One-off probe: the rendered page shows real slot data (times + court
counts) with NO extra XHR/fetch beyond analytics -- so the data must
already be present in the plain server-rendered HTML response. Find
exactly where/how it's embedded."""
import re
import sys

import requests

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
    print(f"STATUS: {r.status_code}  LEN: {len(html)}")

    # Look for any embedded data / hydration markers across common frameworks.
    markers = [
        "__NEXT_DATA__", "__NUXT__", "__INITIAL_STATE__", "__TSR", "__ROUTER",
        "dehydrated", "queryClient", "RSC_PAYLOAD", "__staticRouterHydrationData",
        "type=\"application/json\"", "id=\"__", "window.__",
    ]
    print("\n--- MARKER SCAN ---")
    for m in markers:
        count = html.count(m)
        if count:
            print(f"{m!r}: {count} occurrence(s)")
            idx = html.find(m)
            lo, hi = max(0, idx - 100), min(len(html), idx + 400)
            print("  context:", html[lo:hi].replace("\n", " "))

    # Look for the actual slot times we saw rendered ("18:00", "19:00", "20:00")
    # and dump generous context so we can see the surrounding markup structure.
    print("\n--- TIME SLOT CONTEXT ---")
    for t in ["18:00", "19:00", "20:00"]:
        idx = html.find(t)
        if idx == -1:
            print(f"{t}: NOT FOUND in raw HTML")
            continue
        lo, hi = max(0, idx - 300), min(len(html), idx + 300)
        print(f"\n{t} found at offset {idx}:")
        print(html[lo:hi])

    print("\n--- 'Highbury' CONTEXT (first 3 occurrences) ---")
    for m in list(re.finditer("Highbury", html))[:3]:
        lo, hi = max(0, m.start() - 200), min(len(html), m.start() + 200)
        print(f"\nat offset {m.start()}:")
        print(html[lo:hi])

    return 0


if __name__ == "__main__":
    sys.exit(main())
