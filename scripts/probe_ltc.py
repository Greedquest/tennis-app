#!/usr/bin/env python3
"""Throwaway probe: inspect how localtenniscourts.com loads its availability data.

Loads the query page in a real browser (Playwright/Chromium) and records every
network response (any host), plus a dump of the rendered availability table.
Meant to be run once from a GitHub Actions runner (the sandbox proxy blocks
this domain) to answer: does the site expose a JSON endpoint, or is scraping
the rendered HTML the only option?

v2: v1 only logged responses whose URL contained "localtenniscourts.com",
which would have hidden a data API hosted on a different domain (e.g. a
Supabase/backend host). This version logs every response host+status, and
fetches bodies for anything that looks like data (JSON content-type, or a
non-static-asset extension).

Usage: python scripts/probe_ltc.py
"""

import json
import sys
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

STATIC_EXTENSIONS = (
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".webmanifest",
)


def is_static_asset(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(STATIC_EXTENSIONS)


def main() -> int:
    all_responses: list[dict] = []
    data_responses: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_response(response):
            ctype = ""
            try:
                ctype = response.headers.get("content-type", "")
            except Exception:
                pass

            all_responses.append(
                {"url": response.url, "status": response.status, "content_type": ctype}
            )

            if is_static_asset(response.url) or "google-analytics" in response.url:
                return

            body_snippet = None
            try:
                if "json" in ctype.lower() or "text" in ctype.lower():
                    body_snippet = response.text()[:6000]
            except Exception as e:  # noqa: BLE001 - diagnostic only
                body_snippet = f"<could not read body: {e}>"

            data_responses.append(
                {
                    "url": response.url,
                    "status": response.status,
                    "content_type": ctype,
                    "body_snippet": body_snippet,
                }
            )

        page.on("response", on_response)

        print(f"Navigating to {URL}", file=sys.stderr)
        page.goto(URL, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(3000)  # let any late XHRs settle

        html = page.content()

        # Try to grab the rendered table's outerHTML directly, which is more
        # useful than grepping the full page HTML.
        table_html = None
        try:
            table_html = page.eval_on_selector("table", "el => el.outerHTML")
        except Exception as e:  # noqa: BLE001 - diagnostic only
            table_html = f"<no table found: {e}>"

        browser.close()

    print("\n--- ALL RESPONSE HOSTS (url, status, content-type) ---")
    for r in all_responses:
        print(f"{r['status']:4} {r['content_type']:40} {r['url']}")

    print("\n--- NON-STATIC RESPONSE BODIES (candidate data/API calls) ---")
    print(json.dumps(data_responses, indent=2, default=str))

    print("\n--- RENDERED TABLE outerHTML ---")
    print(table_html)

    print("\n--- RENDERED HTML LENGTH ---")
    print(len(html))

    return 0


if __name__ == "__main__":
    sys.exit(main())
