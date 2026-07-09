#!/usr/bin/env python3
"""Probe https://localtenniscourts.com's real network traffic with a headless browser.

Throwaway diagnostic: the sandbox that authors this repo's code can't reach
localtenniscourts.com directly (proxy 403s it), so this script is meant to be
run somewhere with real network egress (a GitHub Actions job) so its output
can be read back as logs. Not wired into the app — delete once the site's
data shape is understood.

Static regex over the minified Vite bundles turned up nothing (no fetch/api/
venue-name literals), so instead of guessing from source, load the page in a
real browser and record every request/response it actually makes — this is
the only reliable way to find the data endpoint for a heavily minified SPA.
"""

import sys

from playwright.sync_api import sync_playwright

PAGE_URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

# Requests to these are noise (analytics/ads/fonts/etc) - print but don't dump bodies.
NOISE_HOSTS = (
    "googletagmanager.com",
    "google-analytics.com",
    "doubleclick.net",
    "googlesyndication.com",
    "googleadservices.com",
    "google.com",
    "facebook.com",
    "buymeacoffee.com",
    "cloudflareinsights.com",
    "youtube.com",
    "cloudflare.com",
    "merchant-center-analytics.goog",
)


def is_noise(url: str) -> bool:
    return any(h in url for h in NOISE_HOSTS)


def main() -> int:
    requests_log = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        def on_request(req):
            requests_log.append({"type": "request", "method": req.method, "url": req.url, "resource_type": req.resource_type})

        def on_response(res):
            requests_log.append({"type": "response", "status": res.status, "url": res.url})

        page.on("request", on_request)
        page.on("response", on_response)

        print(f"Navigating to {PAGE_URL}")
        page.goto(PAGE_URL, wait_until="networkidle", timeout=30000)
        # Give any lazy XHRs (e.g. triggered after render) a moment to fire.
        page.wait_for_timeout(4000)

        print("\n--- page title ---")
        print(page.title())

        print("\n--- rendered body innerText (first 4000 chars) ---")
        try:
            print(page.inner_text("body")[:4000])
        except Exception as e:
            print(f"(failed: {e})")

        print("\n--- waiting another 8s in case of delayed/debounced fetch ---")
        page.wait_for_timeout(8000)
        print(f"total network events now: {len(requests_log)}")

        print(f"\n--- {len(requests_log)} network events captured ---")
        xhr_fetch = [
            e for e in requests_log if e["type"] == "request" and e["resource_type"] in ("xhr", "fetch")
        ]
        print(f"\n--- {len(xhr_fetch)} XHR/fetch request(s) ---")
        for e in xhr_fetch:
            print(f"{e['method']:6} {e['url']}")

        print("\n--- ALL non-noise requests (any resource type) ---")
        for e in requests_log:
            if e["type"] != "request":
                continue
            if is_noise(e["url"]):
                continue
            print(f"{e['resource_type']:10} {e['method']:6} {e['url']}")

        # For the interesting XHR/fetch calls, try to capture and print the
        # response body (likely JSON with court availability).
        print("\n--- attempting to fetch response bodies for XHR/fetch URLs ---")
        seen = set()
        for e in xhr_fetch:
            if e["url"] in seen:
                continue
            seen.add(e["url"])
            try:
                resp = context.request.get(e["url"])
                body = resp.text()
                print(f"\nURL: {e['url']}")
                print(f"status={resp.status} bytes={len(body)}")
                print(body[:3000])
            except Exception as ex:
                print(f"URL: {e['url']} -> ERROR {ex}")

        browser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
