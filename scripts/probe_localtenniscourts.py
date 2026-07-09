#!/usr/bin/env python3
"""Probe https://localtenniscourts.com to find out how it serves availability data.

Throwaway diagnostic: the sandbox that authors this repo's code can't reach
localtenniscourts.com directly (proxy 403s it), so this script is meant to be
run somewhere with real network egress (a GitHub Actions job) so its output
can be read back as logs. Not wired into the app — delete once the site's
data shape is understood.

Prints:
  - status code and byte length of the page fetched with a browser UA
  - any embedded JSON blobs (Next.js __NEXT_DATA__, __NUXT__, or similar)
  - any <script src> references, fetched in turn and grepped for API-looking
    paths (/api/, .json, graphql)
"""

import json
import re
import sys

import requests

PAGE_URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

API_PATTERN = re.compile(r"""["'](/[a-zA-Z0-9_\-./]*(?:api|graphql|\.json)[a-zA-Z0-9_\-./?=&%]*)["']""")
NEXT_DATA_PATTERN = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)


def fetch(url: str) -> requests.Response:
    return requests.get(url, headers=HEADERS, timeout=20)


def main() -> int:
    print(f"GET {PAGE_URL}")
    r = fetch(PAGE_URL)
    print(f"status={r.status_code} bytes={len(r.content)}")
    text = r.text

    m = NEXT_DATA_PATTERN.search(text)
    if m:
        print("\n--- __NEXT_DATA__ found ---")
        try:
            data = json.loads(m.group(1))
            print(json.dumps(data, indent=2)[:8000])
        except Exception as e:
            print(f"(failed to parse: {e})")
            print(m.group(1)[:4000])
    else:
        print("\n--- no __NEXT_DATA__ blob found ---")

    api_paths = sorted(set(API_PATTERN.findall(text)))
    print(f"\n--- {len(api_paths)} candidate API-looking path(s) in HTML ---")
    for p in api_paths:
        print(p)

    script_srcs = sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', text)))
    print(f"\n--- {len(script_srcs)} <script src> reference(s) ---")
    for src in script_srcs:
        print(src)

    print("\n--- fetching JS bundles for API path hints ---")
    for src in script_srcs:
        url = src if src.startswith("http") else f"https://localtenniscourts.com{src}"
        try:
            jr = fetch(url)
            found = sorted(set(API_PATTERN.findall(jr.text)))
            print(f"{url}: status={jr.status_code} bytes={len(jr.content)} api_paths={found[:20]}")
        except Exception as e:
            print(f"{url}: ERROR {e}")

    print("\n--- first 3000 chars of raw HTML (fallback context) ---")
    print(text[:3000])

    return 0


if __name__ == "__main__":
    sys.exit(main())
