#!/usr/bin/env python3
"""Throwaway probe: render localtenniscourts.com with a real browser and
capture the actual network requests it fires, to find the underlying data
API. Not part of the app — run once on a GitHub Actions runner, read logs,
then delete this file and its workflow.
"""

import sys

from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        requests_seen = []

        def on_request(req):
            requests_seen.append((req.method, req.url, req.resource_type))

        responses_seen = []

        def on_response(resp):
            ct = resp.headers.get("content-type", "")
            if "json" in ct or resp.request.resource_type in ("xhr", "fetch"):
                body_snippet = ""
                try:
                    body_snippet = resp.text()[:1500]
                except Exception as e:
                    body_snippet = f"<no body: {e}>"
                responses_seen.append((resp.status, resp.url, ct, body_snippet))

        page.on("request", on_request)
        page.on("response", on_response)

        print(f"Navigating to {URL}")
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        print("\n--- all requests (method, url, resource_type) ---")
        for method, url, rtype in requests_seen:
            print(f"{method:5} {rtype:8} {url}")

        print("\n--- JSON / xhr / fetch responses (status, url, content-type) ---")
        for status, url, ct, body in responses_seen:
            print(f"\n=== {status} {ct} {url} ===")
            print(body)

        print("\n--- page title ---")
        print(page.title())

        print("\n--- visible text sample (first 2000 chars of body innerText) ---")
        try:
            text = page.inner_text("body")
            print(text[:2000])
        except Exception as e:
            print(f"<error: {e}>")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
