#!/usr/bin/env python3
"""Throwaway probe: inspect how localtenniscourts.com loads its availability data.

Loads the query page in a real browser (Playwright/Chromium) and records every
network response whose URL or content-type looks like a data/API call, plus a
snippet of the rendered HTML. Meant to be run once from a GitHub Actions
runner (the sandbox proxy blocks this domain) to answer: does the site expose
a JSON endpoint, or is scraping the rendered HTML the only option?

Usage: python scripts/probe_ltc.py
"""

import json
import sys

from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

INTERESTING_HINTS = ("api", "json", "graphql", "ajax", "wp-json", "availability", "court", "slot")


def looks_interesting(url: str, content_type: str) -> bool:
    lowered = url.lower()
    if "json" in content_type.lower():
        return True
    return any(hint in lowered for hint in INTERESTING_HINTS)


def main() -> int:
    responses: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_response(response):
            try:
                ctype = response.headers.get("content-type", "")
            except Exception:
                ctype = ""
            if looks_interesting(response.url, ctype) and "localtenniscourts.com" in response.url:
                body_snippet = None
                try:
                    if "json" in ctype.lower():
                        body_snippet = response.text()[:4000]
                except Exception as e:  # noqa: BLE001 - diagnostic only
                    body_snippet = f"<could not read body: {e}>"
                responses.append(
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
        with open("/tmp/ltc_rendered.html", "w", encoding="utf-8") as f:
            f.write(html)

        browser.close()

    print("\n--- INTERESTING NETWORK RESPONSES ---")
    print(json.dumps(responses, indent=2, default=str))

    print("\n--- RENDERED HTML LENGTH ---")
    print(len(html))

    print("\n--- RENDERED HTML SNIPPET (first 6000 chars) ---")
    print(html[:6000])

    # Look for Wednesday-shaped text anywhere in the rendered DOM as a sanity check
    print("\n--- 'wed' MENTIONS IN RENDERED HTML ---")
    lowered_html = html.lower()
    idx = 0
    count = 0
    while count < 10:
        idx = lowered_html.find("wed", idx)
        if idx == -1:
            break
        print(html[max(0, idx - 60) : idx + 60].replace("\n", " "))
        idx += 3
        count += 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
