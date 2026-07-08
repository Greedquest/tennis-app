#!/usr/bin/env python3
"""THROWAWAY probe: inspect localtenniscourts.com for a JSON API.

Not part of the app. Run once on a real-network runner (GitHub Actions) to
capture the network requests a browser makes when loading the page, so we
can decide whether to hit a JSON endpoint directly or fall back to scraping.
Delete after use.
"""

import json
import re

from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

requests_seen = []
json_bodies = []


def on_request(request):
    requests_seen.append(f"{request.method} {request.resource_type} {request.url}")


def on_response(response):
    ctype = response.headers.get("content-type", "")
    if "json" in ctype:
        try:
            body = response.text()
        except Exception as e:  # noqa: BLE001
            body = f"<error reading body: {e}>"
        json_bodies.append((response.url, response.status, ctype, body[:4000]))


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("request", on_request)
        page.on("response", on_response)

        print(f"Navigating to {URL}")
        try:
            page.goto(URL, wait_until="networkidle", timeout=30000)
        except Exception as e:  # noqa: BLE001
            print(f"goto() raised: {e} -- continuing with whatever loaded")

        page.wait_for_timeout(3000)  # give any lazy XHRs a chance to fire

        title = page.title()
        html = page.content()
        browser.close()

    print("\n=== PAGE TITLE ===")
    print(title)

    print("\n=== ALL NETWORK REQUESTS ===")
    for r in requests_seen:
        print(r)

    print("\n=== JSON RESPONSES ===")
    if not json_bodies:
        print("(none captured)")
    for url, status, ctype, body in json_bodies:
        print(f"\n--- {status} {ctype} {url} ---")
        print(body)

    print("\n=== EMBEDDED JSON BLOBS IN HTML (script tags / window.__*) ===")
    next_data = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
    )
    if next_data:
        print("--- __NEXT_DATA__ ---")
        print(next_data.group(1)[:4000])

    for m in re.finditer(r"window\.__[A-Za-z_]+\s*=\s*(\{.*?\});", html, re.DOTALL):
        print("--- window.__* assignment ---")
        print(m.group(1)[:2000])

    print("\n=== SCRIPT SRC TAGS (JS bundles worth checking for API base URLs) ===")
    for m in re.finditer(r'<script[^>]+src="([^"]+)"', html):
        print(m.group(1))

    print("\n=== RAW HTML (first 3000 chars) ===")
    print(html[:3000])

    print("\n=== RAW HTML (contains 'wednesday'/'19:00'/'highbury'/'islington' snippets) ===")
    for kw in ("wednesday", "19:00", "highbury", "islington", "api/"):
        idxs = [m.start() for m in re.finditer(re.escape(kw), html, re.IGNORECASE)]
        print(f"'{kw}': {len(idxs)} occurrence(s)")
        for i in idxs[:3]:
            print(f"  ...{html[max(0, i - 80): i + 80]}...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
