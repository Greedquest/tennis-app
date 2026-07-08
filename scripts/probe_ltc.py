#!/usr/bin/env python3
"""Throwaway probe: inspect localtenniscourts.com for a JSON API vs HTML-only.

Run from an environment with real network egress (this sandbox's proxy 403s
arbitrary domains — see CLAUDE.md gotchas). Prints:
  1. The raw HTML of the query page (truncated), so we can grep for
     script/fetch/XHR hints pointing at a JSON endpoint.
  2. A few common API-path guesses, each fetched and status-reported.

Delete this script (and its throwaway workflow) once the real answer is
known and wired into tennis_app/.
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

API_GUESSES = [
    "https://localtenniscourts.com/api/courts",
    "https://localtenniscourts.com/api/venues",
    "https://localtenniscourts.com/api/search",
    "https://localtenniscourts.com/wp-json/",
    "https://localtenniscourts.com/wp-json/wp/v2/venues",
]


def main() -> int:
    print(f"=== GET {PAGE_URL} ===")
    try:
        r = requests.get(PAGE_URL, headers=HEADERS, timeout=20)
        print(f"status={r.status_code} content-type={r.headers.get('content-type')} bytes={len(r.content)}")
        html = r.text

        print("\n--- lines mentioning api / json / fetch / xhr / axios / .json ---")
        for i, line in enumerate(html.splitlines()):
            if re.search(r"(api[/_-]|\.json|fetch\(|XMLHttpRequest|axios|graphql)", line, re.I):
                snippet = line.strip()[:300]
                print(f"{i:5}: {snippet}")

        print("\n--- <script src=...> tags ---")
        for m in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.I):
            print(m.group(1))

        print(f"\n--- first 3000 chars of body ---\n{html[:3000]}")
    except Exception as e:  # noqa: BLE001 - diagnostic script
        print(f"ERROR fetching page: {e}")

    print("\n=== API path guesses ===")
    for url in API_GUESSES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            print(f"{r.status_code:4} {url} content-type={r.headers.get('content-type')} bytes={len(r.content)}")
            if "json" in (r.headers.get("content-type") or ""):
                print(f"      body[:500]={r.text[:500]}")
        except Exception as e:  # noqa: BLE001
            print(f" ERR  {url}  {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
