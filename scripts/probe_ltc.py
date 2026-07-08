#!/usr/bin/env python3
"""Throwaway probe v3: why doesn't the availability table have any rows?

v1/v2 showed: the rendered <table> has day-of-week headers (Wed 08, Thu 09,
...) but no <tbody> rows, and no XHR/fetch response was ever observed to any
host. This version waits longer, logs every *request* (not just responses),
console messages, and page errors, and dumps the full un-truncated initial
HTML body to a log-friendly (base64-chunked) form so we can tell whether the
app ever attempts a data fetch at all.

Usage: python scripts/probe_ltc.py
"""

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
    requests_log: list[str] = []
    console_log: list[str] = []
    errors_log: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        page.on(
            "request",
            lambda req: requests_log.append(f"{req.method} {req.url}")
            if not is_static_asset(req.url)
            else None,
        )
        page.on("console", lambda msg: console_log.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda exc: errors_log.append(str(exc)))

        print(f"Navigating to {URL}", file=sys.stderr)
        page.goto(URL, wait_until="load", timeout=45000)

        # Poll for table rows for up to 15s instead of a single fixed wait
        found_rows = False
        for _ in range(15):
            page.wait_for_timeout(1000)
            try:
                n_rows = page.eval_on_selector_all("table tbody tr", "els => els.length")
            except Exception:
                n_rows = 0
            if n_rows:
                found_rows = True
                print(f"Rows appeared after ~{_+1}s: {n_rows} rows", file=sys.stderr)
                break

        html = page.content()

        table_html = None
        try:
            table_html = page.eval_on_selector("table", "el => el.outerHTML")
        except Exception as e:  # noqa: BLE001
            table_html = f"<no table found: {e}>"

        # Grab any text mentioning "no results", "error", "loading" etc as a hint
        body_text = page.inner_text("body")

        browser.close()

    print(f"\n--- FOUND ROWS: {found_rows} ---")

    print("\n--- NON-STATIC REQUESTS (method + url) ---")
    for r in requests_log:
        print(r)

    print("\n--- CONSOLE MESSAGES ---")
    for c in console_log:
        print(c)

    print("\n--- PAGE ERRORS ---")
    for e in errors_log:
        print(e)

    print("\n--- FULL TABLE outerHTML ---")
    print(table_html)

    print("\n--- BODY INNER TEXT (first 3000 chars) ---")
    print(body_text[:3000])

    print("\n--- RENDERED HTML LENGTH ---")
    print(len(html))

    return 0


if __name__ == "__main__":
    sys.exit(main())
