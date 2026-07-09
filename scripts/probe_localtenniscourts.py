#!/usr/bin/env python3
"""Probe https://localtenniscourts.com to find out how it serves availability data.

Throwaway diagnostic: the sandbox that authors this repo's code can't reach
localtenniscourts.com directly (proxy 403s it), so this script is meant to be
run somewhere with real network egress (a GitHub Actions job) so its output
can be read back as logs. Not wired into the app — delete once the site's
data shape is understood.

The site is a Vite SPA (no server-rendered data blob), so the real logic
lives in its JS bundles referenced via <link rel="modulepreload">. This
probe fetches the page, follows every <script src> AND modulepreload/
stylesheet link under /assets/, and grep for anything that looks like a
backend call: absolute API hosts, fetch()/axios calls, graphql, .json.
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

API_PATTERN = re.compile(
    r"""["'](https?://[a-zA-Z0-9_.\-]+\.[a-zA-Z]{2,}(?:/[a-zA-Z0-9_\-./?=&%]*)?|/[a-zA-Z0-9_\-./]*(?:api|graphql|\.json)[a-zA-Z0-9_\-./?=&%]*)["']"""
)
NEXT_DATA_PATTERN = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


def fetch(url: str) -> requests.Response:
    return requests.get(url, headers=HEADERS, timeout=20)


def absolutize(src: str) -> str:
    if src.startswith("http"):
        return src
    return f"https://localtenniscourts.com{src}"


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

    # Collect every JS asset the page references: <script src>, modulepreload
    # links, and stylesheet links (skip css, keep js).
    script_srcs = set(re.findall(r'<script[^>]+src="([^"]+)"', text))
    preload_srcs = set(re.findall(r'<link rel="modulepreload" href="([^"]+)"', text))
    all_js = sorted(script_srcs | preload_srcs)

    print(f"\n--- {len(all_js)} JS asset reference(s) ---")
    for src in all_js:
        print(src)

    print("\n--- fetching JS bundles for API path hints ---")
    all_hits: dict[str, list[str]] = {}
    for src in all_js:
        url = absolutize(src)
        try:
            jr = fetch(url)
            found = sorted(set(API_PATTERN.findall(jr.text)))
            # third-party noise we don't care about
            found = [
                f
                for f in found
                if not any(
                    noise in f
                    for noise in (
                        "googletagmanager",
                        "google-analytics",
                        "cloudflare",
                        "buymeacoffee",
                        "w3.org",
                        "schema.org",
                    )
                )
            ]
            all_hits[url] = found
            print(f"{url}: status={jr.status_code} bytes={len(jr.content)} hits={len(found)}")
        except Exception as e:
            print(f"{url}: ERROR {e}")

    print("\n--- filtered candidate backend URLs/paths, by bundle ---")
    for url, hits in all_hits.items():
        if hits:
            print(f"\n{url}:")
            for h in hits:
                print(f"  {h}")

    # Also grep raw bundle text for common client patterns even if the
    # regex above missed it (relative fetch("/something") calls, etc).
    print("\n--- raw grep for fetch(/axios/supabase/graphql mentions ---")
    for src in all_js:
        url = absolutize(src)
        try:
            jr = fetch(url)
            for pattern in ("supabase", "graphql", ".rpc(", "fetch(`", "fetch('", 'fetch("', "axios."):
                idx = jr.text.find(pattern)
                if idx != -1:
                    snippet = jr.text[max(0, idx - 80) : idx + 200]
                    print(f"{url} :: pattern={pattern!r}\n  ...{snippet}...")
        except Exception:
            pass

    print("\n--- first 3000 chars of raw HTML (fallback context) ---")
    print(text[:3000])

    return 0


if __name__ == "__main__":
    sys.exit(main())
