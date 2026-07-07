#!/usr/bin/env python3
"""One-off probe: drive localtenniscourts.com with a headless browser and
capture every network request it makes, to find the underlying data API."""
import json
import sys

from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"


def main() -> int:
    requests_seen = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_request(req):
            requests_seen.append({"method": req.method, "url": req.url, "resource_type": req.resource_type})

        def on_response(res):
            if res.request.resource_type in ("xhr", "fetch"):
                try:
                    body_preview = res.text()[:1500]
                except Exception as e:
                    body_preview = f"<unreadable: {e}>"
                print(f"\n=== RESPONSE {res.status} {res.request.method} {res.url} ===")
                print(f"content-type: {res.headers.get('content-type')}")
                print(body_preview)

        page.on("request", on_request)
        page.on("response", on_response)

        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        browser.close()

    print("\n\n=== ALL REQUESTS (non-static) ===")
    for r in requests_seen:
        if r["resource_type"] in ("xhr", "fetch", "document"):
            print(f"{r['resource_type']:10} {r['method']:5} {r['url']}")

    print("\n=== ALL REQUESTS (full, JSON) ===")
    print(json.dumps(requests_seen, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
