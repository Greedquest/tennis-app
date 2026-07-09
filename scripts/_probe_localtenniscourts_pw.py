#!/usr/bin/env python3
"""Throwaway probe: render localtenniscourts.com with a real browser and
capture the actual network requests it fires, to find the underlying data
API. Not part of the app — run once on a GitHub Actions runner, read logs,
then delete this file and its workflow.

v2: listen at the BrowserContext level (catches requests from service
workers / dedicated workers that page-level listeners can miss), and log
requestfailed to see blocked/CORS/DNS-failed calls the app attempted.
"""

import sys

from playwright.sync_api import sync_playwright

URLS = [
    "https://localtenniscourts.com/",
]


def probe_one(context, url: str) -> None:
    print(f"\n\n########## {url} ##########")
    page = context.new_page()

    requests_seen = []
    failed_seen = []
    responses_seen = []
    console_msgs = []

    def on_request(req):
        requests_seen.append((req.method, req.url, req.resource_type))

    def on_requestfailed(req):
        failed_seen.append((req.method, req.url, req.resource_type, req.failure))

    def on_response(resp):
        ct = resp.headers.get("content-type", "")
        if "json" in ct or resp.request.resource_type in ("xhr", "fetch"):
            body_snippet = ""
            try:
                body_snippet = resp.text()[:1500]
            except Exception as e:
                body_snippet = f"<no body: {e}>"
            responses_seen.append((resp.status, resp.url, ct, body_snippet))

    def on_console(msg):
        console_msgs.append(f"[{msg.type}] {msg.text}")

    context.on("request", on_request)
    context.on("requestfailed", on_requestfailed)
    context.on("response", on_response)
    page.on("console", on_console)
    page.on("pageerror", lambda exc: console_msgs.append(f"[pageerror] {exc}"))

    print(f"Navigating to {url}")
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(4000)

    print("\n--- all requests (method, url, resource_type) ---")
    for method, req_url, rtype in requests_seen:
        print(f"{method:5} {rtype:8} {req_url}")

    print("\n--- FAILED requests (method, url, resource_type, failure) ---")
    for method, req_url, rtype, failure in failed_seen:
        print(f"{method:5} {rtype:8} {req_url}  FAILURE={failure}")

    print("\n--- JSON / xhr / fetch responses (status, url, content-type) ---")
    for status, resp_url, ct, body in responses_seen:
        print(f"\n=== {status} {ct} {resp_url} ===")
        print(body)

    print("\n--- console / page errors ---")
    for m in console_msgs:
        print(m)

    print("\n--- page title ---")
    print(page.title())

    print("\n--- visible text sample (first 2000 chars of body innerText) ---")
    try:
        text = page.inner_text("body")
        print(text[:2000])
    except Exception as e:
        print(f"<error: {e}>")

    print("\n--- service workers registered? ---")
    try:
        print(context.service_workers)
    except Exception as e:
        print(f"<error: {e}>")

    page.close()


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        for url in URLS:
            probe_one(context, url)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
