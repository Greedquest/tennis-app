#!/usr/bin/env python3
"""Throwaway probe: inspect localtenniscourts.com for a JSON API or embedded data.

Not meant to be kept in the repo -- run once on a GitHub Actions runner (real
egress), read the logs, then delete this file + its workflow.
"""

import json
import re
import sys

import requests

BASE = "https://localtenniscourts.com"
QUERY_URL = f"{BASE}/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}


def dump_response(label: str, r: requests.Response) -> None:
    print(f"\n=== {label} ===")
    print("status:", r.status_code)
    print("content-type:", r.headers.get("content-type"))
    print("content-length:", len(r.content))
    print("headers:", dict(r.headers))


def main() -> int:
    r = requests.get(QUERY_URL, headers=HEADERS, timeout=20)
    dump_response("GET / (query page)", r)
    body = r.text

    print("\n--- first 3000 chars of body ---")
    print(body[:3000])

    # Look for <script> tags, especially JSON payloads (Next.js __NEXT_DATA__,
    # Nuxt __NUXT__, inline state, etc.)
    script_srcs = re.findall(r'<script[^>]*\ssrc=["\']([^"\']+)["\']', body, re.I)
    print("\n--- script src attributes ---")
    for s in script_srcs:
        print(s)

    json_scripts = re.findall(
        r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
        body,
        re.I | re.S,
    )
    print(f"\n--- {len(json_scripts)} inline application/json script block(s) ---")
    for i, block in enumerate(json_scripts):
        print(f"[block {i}] length={len(block)}")
        print(block[:2000])

    for marker in ("__NEXT_DATA__", "__NUXT__", "window.__INITIAL_STATE__", "ApolloState"):
        if marker in body:
            print(f"\nFound marker: {marker}")

    api_like = sorted(set(re.findall(r'["\'](/api/[^"\']+|https?://[^"\']*/api/[^"\']+)["\']', body)))
    print(f"\n--- {len(api_like)} /api/-looking string(s) referenced in HTML ---")
    for a in api_like:
        print(a)

    # Try a couple of plausible JSON endpoints directly.
    candidates = [
        f"{BASE}/api/courts",
        f"{BASE}/api/venues",
        f"{BASE}/api/search",
        f"{BASE}/api/search?q=highbury-fields,islington-tennis-centre-outdoor",
        f"{BASE}/_next/data",
    ]
    for url in candidates:
        try:
            rr = requests.get(url, headers=HEADERS, timeout=10)
            print(f"\nprobe {url} -> {rr.status_code} ({rr.headers.get('content-type')}, {len(rr.content)}B)")
            if rr.ok and "json" in (rr.headers.get("content-type") or ""):
                try:
                    print(json.dumps(rr.json(), indent=2)[:1500])
                except Exception:
                    print(rr.text[:500])
        except Exception as e:
            print(f"\nprobe {url} -> ERROR {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
