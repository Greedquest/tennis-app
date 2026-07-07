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

    # 2. Find script src references + modulepreload links (Vite emits these, not <script src>)
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
    modulepreloads = re.findall(r'<link rel="modulepreload" href="([^"]+)"', html)
    print("\n--- SCRIPT SRCS ---")
    for s in scripts:
        print(s)
    print("\n--- MODULEPRELOAD HREFS ---")
    for m in modulepreloads:
        print(m)
    scripts = scripts + modulepreloads

    # 3. Find any /api/ or json-looking paths mentioned in the HTML
    api_like = sorted(set(re.findall(r'["\'](/[a-zA-Z0-9_\-./]*api[a-zA-Z0-9_\-./]*)["\']', html)))
    print("\n--- API-LIKE PATHS IN HTML ---")
    for a in api_like:
        print(a)

    # 4. Dump a snippet of raw HTML for manual inspection (first 3000 chars)
    print("\n--- HTML HEAD SNIPPET ---")
    print(html[:3000])

    # 5. Fetch same-origin JS bundles (main.js, index.js, etc.) and grep broadly for
    #    anything that looks like a backend call: absolute https URLs, fetch/axios
    #    calls, supabase/firebase/graphql hints, or literal "api" substrings.
    print("\n--- SCANNING JS BUNDLES FOR ENDPOINTS ---")
    base = "https://localtenniscourts.com"
    same_origin = [s for s in scripts if s.startswith("/") or base in s]
    for s in same_origin:
        src = s if s.startswith("http") else f"{base}{s}"
        try:
            jr = requests.get(src, headers=HEADERS, timeout=20)
            text = jr.text
            print(f"\n{src} ({len(text)} bytes)")

            abs_urls = sorted(set(re.findall(r'https?://[a-zA-Z0-9_\-./%]+', text)))
            non_asset_urls = [
                u for u in abs_urls
                if "localtenniscourts.com" not in u
                and not any(u.endswith(ext) for ext in (".png", ".jpg", ".svg", ".ico", ".woff", ".woff2"))
                and "w3.org" not in u
            ]
            if non_asset_urls:
                print("  absolute URLs referenced:")
                for u in non_asset_urls[:60]:
                    print("   ", u)

            for kw in ["supabase", "firebase", "graphql", "fetch(", "axios", "/api", "cloudflare", "worker", ".workers.dev"]:
                count = text.count(kw)
                if count:
                    print(f"  keyword {kw!r}: {count} occurrence(s)")

        except Exception as e:
            print(f"  ERR fetching {src}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
