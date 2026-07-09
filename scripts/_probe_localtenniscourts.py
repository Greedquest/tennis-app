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

    # The page is a client-rendered SPA (no __NEXT_DATA__/__NUXT__, day names
    # absent from server HTML) — the real data must be fetched by the JS
    # bundles at runtime. Pull those bundles and grep them for API endpoints.
    bundle_paths = sorted(set(re.findall(r'(/assets/[^"\']+\.js)', text)))
    print("\n--- JS bundle paths found in HTML ---")
    for p in bundle_paths:
        print(p)

    for bp in bundle_paths:
        bundle_url = "https://localtenniscourts.com" + bp
        print(f"\n=== fetching bundle {bundle_url} ===")
        try:
            br = requests.get(bundle_url, headers=HEADERS, timeout=20)
            print(f"status={br.status_code} len={len(br.text)}")
            btext = br.text

            print(f"--- {bp}: absolute https:// URLs (deduped, first 40) ---")
            found_urls = sorted(set(re.findall(r'https?://[a-zA-Z0-9_./-]+', btext)))
            for u in found_urls[:40]:
                print(u)

            print(f"--- {bp}: relative /api-ish path literals ---")
            for m in sorted(set(re.findall(r'["\'](/[a-zA-Z0-9_/-]*(?:api|rpc|graphql)[a-zA-Z0-9_/-]*)["\']', btext, re.I))):
                print(m)

            print(f"--- {bp}: supabase/firebase/airtable/wix hints ---")
            for kw in ["supabase", "firebase", "airtable", "wix", ".workers.dev", "vercel", "amazonaws", "googleapis"]:
                if kw in btext.lower():
                    idx = btext.lower().find(kw)
                    print(f"{kw}: ...{btext[max(0, idx-80):idx+120]}...")

            print(f"--- {bp}: fetch(/axios(/XMLHttpRequest calls with context ---")
            for m in re.finditer(r"(fetch|axios\.\w+|\.get\(|\.post\()\s*\(", btext):
                start = max(0, m.start() - 20)
                print("..." + btext[start : m.start() + 160].replace("\n", " ") + "...")

            print(f"--- {bp}: short path-like string literals (dedup, up to 80) ---")
            paths = sorted(set(re.findall(r'["\']((?:/[a-zA-Z0-9_.-]+){1,4})["\']', btext)))
            paths = [p for p in paths if not p.startswith("/assets/") and len(p) < 40]
            for p in paths[:80]:
                print(p)
        except Exception as e:
            print(f"ERR fetching {bundle_url}: {e}")

    print("\n--- direct probes of common data-endpoint guesses on the same origin ---")
    guesses = [
        "/api/courts",
        "/api/availability",
        "/api/venues",
        "/api/slots",
        "/api/data",
        "/courts.json",
        "/data.json",
        "/data/courts.json",
        "/availability.json",
        "/export.json",
        "/slots.json",
        "/robots.txt",
        "/sitemap.xml",
    ]
    for g in guesses:
        try:
            gr = requests.get("https://localtenniscourts.com" + g, headers=HEADERS, timeout=15)
            print(f"{gr.status_code:4} len={len(gr.content):7}  {g}  content-type={gr.headers.get('content-type')}")
        except Exception as e:
            print(f" ERR  {g}  {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
