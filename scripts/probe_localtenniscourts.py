#!/usr/bin/env python3
"""THROWAWAY probe: inspect localtenniscourts.com for a JSON API.

Not part of the app. Run once on a real-network runner (GitHub Actions) to
capture the network requests a browser makes when loading the page, so we
can decide whether to hit a JSON endpoint directly or fall back to scraping.
Delete after use.
"""

import re

import requests
from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

requests_seen = []
json_bodies = []


def on_request(request):
    requests_seen.append(f"{request.method} {request.resource_type} {request.url}")


def on_response(response):
    ctype = response.headers.get("content-type", "")
    if "json" in ctype:
        try:
            body = response.text()
        except Exception as e:  # noqa: BLE001
            body = f"<error reading body: {e}>"
        json_bodies.append((response.url, response.status, ctype, body[:4000]))


def plain_requests_check() -> str:
    """Fetch the page with plain requests (no JS execution) to test for SSR."""
    r = requests.get(URL, headers={"User-Agent": UA}, timeout=20)
    print(f"\n=== PLAIN REQUESTS.GET: status={r.status_code} len={len(r.text)} ===")
    has_1900 = "19:00" in r.text
    has_table = "<table" in r.text
    print(f"contains '19:00': {has_1900}   contains '<table': {has_table}")
    return r.text


def dump_table(html: str, label: str) -> None:
    idx = html.find("<table")
    print(f"\n=== {label}: <table> onward (first 12000 chars) ===")
    if idx == -1:
        print("(no <table> tag found)")
        return
    print(html[idx : idx + 12000])


def main() -> int:
    plain_html = plain_requests_check()
    dump_table(plain_html, "PLAIN REQUESTS HTML")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("request", on_request)
        page.on("response", on_response)

        print(f"\nNavigating (browser) to {URL}")
        try:
            page.goto(URL, wait_until="networkidle", timeout=30000)
        except Exception as e:  # noqa: BLE001
            print(f"goto() raised: {e} -- continuing with whatever loaded")

        page.wait_for_timeout(3000)  # give any lazy XHRs a chance to fire

        html = page.content()
        browser.close()

    print("\n=== ALL NETWORK REQUESTS (browser) ===")
    for r in requests_seen:
        print(r)

    print("\n=== JSON RESPONSES (browser) ===")
    if not json_bodies:
        print("(none captured)")
    for url, status, ctype, body in json_bodies:
        print(f"\n--- {status} {ctype} {url} ---")
        print(body)

    dump_table(html, "BROWSER-RENDERED HTML")

    print("\n=== day-of-week / date header search (browser HTML) ===")
    for kw in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
        idxs = [m.start() for m in re.finditer(kw, html)]
        print(f"'{kw}': {len(idxs)} occurrence(s)")
        for i in idxs[:2]:
            print(f"  ...{html[max(0, i - 150): i + 150]}...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
