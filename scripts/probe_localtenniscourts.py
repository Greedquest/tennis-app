#!/usr/bin/env python3
"""Probe localtenniscourts.com to discover its underlying data source.

This sandbox's egress proxy denies localtenniscourts.com outright (403 at
the CONNECT step), so this can only be run somewhere with real internet
access, e.g. a throwaway GitHub Actions job on a runner (see the
"Gotchas" section of CLAUDE.md for the established pattern: push a
probe workflow, read the job logs, then delete the workflow).

It drives a headless browser to the query page, records every network
request the page makes, and prints anything that looks like a JSON/XHR
data call plus a snippet of its response body -- so we can tell whether
the site is backed by a discoverable API or whether HTML scraping is the
only option.
"""

import json
import sys

from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"


def main() -> int:
    calls: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_response(response):
            req = response.request
            if req.resource_type not in ("xhr", "fetch", "document"):
                return
            content_type = response.headers.get("content-type", "")
            entry = {
                "method": req.method,
                "url": response.url,
                "status": response.status,
                "content_type": content_type,
                "resource_type": req.resource_type,
            }
            if "json" in content_type:
                try:
                    body = response.text()
                    entry["body_snippet"] = body[:2000]
                except Exception as e:  # noqa: BLE001 - diagnostic tool
                    entry["body_error"] = str(e)
            calls.append(entry)

        page.on("response", on_response)

        print(f"Navigating to {URL} ...", file=sys.stderr)
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)  # settle any late XHRs

        html = page.content()
        with open("localtenniscourts_rendered.html", "w", encoding="utf-8") as f:
            f.write(html)

        browser.close()

    print("\n--- NETWORK CALLS (JSON) ---")
    print(json.dumps(calls, indent=2, default=str))
    print(f"\nRendered HTML saved to localtenniscourts_rendered.html ({len(html)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
