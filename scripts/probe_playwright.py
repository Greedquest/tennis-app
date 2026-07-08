#!/usr/bin/env python3
"""Throwaway probe: load localtenniscourts.com in headless Chromium and record
every network request it makes, to find the underlying data endpoint.

Static string-grepping the JS bundles (see probe_localtenniscourts.py) found
the data shape (booking_url, total_spaces, freshness, name) but no literal
fetch()/axios() call site — the request is likely built dynamically or lives
in a lazily-loaded chunk. Watching real network traffic settles it.

Run from an environment with real internet egress, read the output, then
delete this file and its probe workflow.
"""

import sys

from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields,islington-tennis-centre-outdoor"


def main() -> int:
    requests_seen = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_request(request):
            requests_seen.append((request.method, request.url))

        def on_response(response):
            ct = response.headers.get("content-type", "")
            if "json" in ct or "xhr" in (response.request.resource_type or ""):
                print(f"RESPONSE {response.status} {ct} {response.url}")

        page.on("request", on_request)
        page.on("response", on_response)

        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)  # give any deferred/polling fetches a chance

        html_snapshot = page.content()
        browser.close()

    print(f"\n--- {len(requests_seen)} total requests captured ---")
    for method, url in requests_seen:
        print(f"{method} {url}")

    print(f"\n--- rendered DOM length: {len(html_snapshot)} ---")
    # Look for rendered court/time text that only appears after JS runs.
    import re

    times = re.findall(r"\b\d{1,2}:\d{2}\s?(?:am|pm|AM|PM)?\b", html_snapshot)
    print(f"--- {len(times)} time-like strings in rendered DOM (first 20) ---")
    for t in times[:20]:
        print(t)

    return 0


if __name__ == "__main__":
    sys.exit(main())
