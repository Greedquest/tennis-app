#!/usr/bin/env python3
"""Throwaway probe: inspect how localtenniscourts.com loads court data.

Not part of the app. Loads the target URL in headless Chromium, records
every network request/response the page makes while rendering, and dumps
anything that looks like a JSON data API alongside a snippet of the
rendered HTML. Meant to be run once (from an environment with real
internet egress, e.g. GitHub Actions) to answer: does this site expose a
JSON endpoint, or do we need to scrape rendered HTML?
"""

import json
import re
import sys

import requests
from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"


def probe_plain_http() -> None:
    """Fetch with a plain GET (no JS) to see if the data is already server-rendered."""
    r = requests.get(URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    print(f"\n--- PLAIN HTTP GET: status={r.status_code} len={len(r.text)} ---")
    # Find the table (or main content) and print a chunk around the first
    # occurrence of a time-like string, so we can see real markup/attributes.
    m = re.search(r"08:00", r.text)
    start = max(0, (m.start() - 500)) if m else 0
    print(r.text[start : start + 6000])


def main() -> int:
    probe_plain_http()

    api_like: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_response(response):
            ct = response.headers.get("content-type", "")
            if "json" in ct.lower():
                entry = {
                    "url": response.url,
                    "status": response.status,
                    "content_type": ct,
                    "request_method": response.request.method,
                }
                try:
                    body = response.text()
                    entry["body_snippet"] = body[:4000]
                except Exception as e:  # noqa: BLE001 - diagnostic tool
                    entry["body_error"] = str(e)
                api_like.append(entry)
                print(f"JSON response: {response.status} {response.request.method} {response.url}")

        page.on("response", on_response)

        print(f"Navigating to {URL}")
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)  # let any lazy XHRs settle

        html = page.content()
        with open("/tmp/ltc_rendered.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Rendered HTML length: {len(html)} (saved to /tmp/ltc_rendered.html)")

        # Print a text-only view of the body to eyeball slot/day structure
        body_text = page.inner_text("body")
        print("\n--- BODY TEXT (first 6000 chars) ---")
        print(body_text[:6000])

        browser.close()

    print("\n--- JSON-LIKE RESPONSES SUMMARY ---")
    print(json.dumps(api_like, indent=2, default=str)[:20000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
