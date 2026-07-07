#!/usr/bin/env python3
"""Throwaway probe: discover how localtenniscourts.com sources its data.

This is NOT part of the app — it's a one-shot reconnaissance script meant to
run somewhere with real internet egress (GitHub Actions), because the dev
sandbox's outbound proxy blocks this domain outright (CONNECT rejected at the
proxy, before it even reaches the site). See the "probe on GitHub Actions"
gotcha in CLAUDE.md for the general pattern this follows.

It loads the page in headless Chromium via Playwright, records every
network request/response the page makes while rendering, and prints:
  - every XHR/fetch request URL, method, and status
  - the body of any JSON responses (so we can see the data shape)
  - a snippet of the final rendered HTML (fallback if there's no JSON API)

Delete this script (and its throwaway workflow) once the API shape is known
and the real fetch/parse code is written against it.
"""

import json
import sys

from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"


def main() -> int:
    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_response(response):
            request = response.request
            if request.resource_type not in ("xhr", "fetch", "document"):
                return
            entry = {
                "url": response.url,
                "method": request.method,
                "status": response.status,
                "resource_type": request.resource_type,
                "content_type": response.headers.get("content-type", ""),
            }
            if "json" in entry["content_type"]:
                try:
                    entry["body"] = response.json()
                except Exception as e:  # noqa: BLE001 - diagnostic tool
                    entry["body_error"] = str(e)
            captured.append(entry)

        page.on("response", on_response)

        print(f"Navigating to {URL}", file=sys.stderr)
        page.goto(URL, wait_until="networkidle", timeout=30000)
        # Give any deferred/polling XHR a moment to fire after networkidle.
        page.wait_for_timeout(3000)

        html = page.content()
        title = page.title()

        browser.close()

    print("\n=== PAGE TITLE ===")
    print(title)

    print("\n=== CAPTURED REQUESTS ===")
    for entry in captured:
        body_note = ""
        if "body" in entry:
            body_note = f"  body={json.dumps(entry['body'])[:2000]}"
        elif "body_error" in entry:
            body_note = f"  body_error={entry['body_error']}"
        print(
            f"{entry['status']:>4} {entry['method']:<5} [{entry['resource_type']:<8}] "
            f"{entry['url']}{body_note}"
        )

    print("\n=== RENDERED HTML LENGTH ===")
    print(len(html))

    print("\n=== RENDERED HTML SNIPPET (first 3000 chars of <body>) ===")
    body_start = html.find("<body")
    print(html[body_start : body_start + 3000] if body_start != -1 else html[:3000])

    print("\n=== RENDERED HTML SNIPPET (search for 'wed' / table rows) ===")
    lower = html.lower()
    idx = lower.find("wed")
    if idx != -1:
        print(html[max(0, idx - 500) : idx + 1500])
    else:
        print("(no 'wed' substring found in rendered HTML)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
