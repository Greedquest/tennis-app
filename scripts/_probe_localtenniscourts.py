#!/usr/bin/env python3
"""Throwaway probe: inspect localtenniscourts.com for a JSON API / data structure.

Not part of the app. Run once on a GitHub Actions runner (real internet egress),
read the logs, then delete this file and its workflow.
"""

import re
import sys

import requests

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def main() -> int:
    print(f"GET {URL}")
    r = requests.get(URL, headers=HEADERS, timeout=20)
    print(f"status={r.status_code} len={len(r.text)}")
    print("content-type:", r.headers.get("content-type"))
    text = r.text

    print("\n--- first 3000 chars ---")
    print(text[:3000])

    print("\n--- script src tags ---")
    for m in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text):
        print(m)

    print("\n--- inline script blocks containing api/json/graphql/fetch/axios ---")
    for m in re.finditer(r"<script[^>]*>(.*?)</script>", text, re.S):
        block = m.group(1)
        if re.search(r"(api/|\.json|graphql|fetch\(|axios|__NEXT_DATA__|__NUXT__)", block, re.I):
            print("----- block -----")
            print(block[:2000])

    print("\n--- any absolute URLs containing api/json/graphql ---")
    for m in set(re.findall(r'https?://[^\s"\'<>]+', text)):
        if re.search(r"(api|\.json|graphql)", m, re.I):
            print(m)

    print("\n--- __NEXT_DATA__ / __NUXT__ presence ---")
    print("__NEXT_DATA__" in text, "__NUXT__" in text, "window.__INITIAL_STATE__" in text)

    print("\n--- looks like day-of-week markers present? ---")
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        print(day, day in text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
