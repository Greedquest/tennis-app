#!/usr/bin/env python3
"""One-off probe: check whether court data is baked into the static bundle
at build time (vs. fetched live) by inspecting rendered DOM text and
searching the JS bundle for date/time-shaped literals."""
import re
import sys

import requests
from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(4000)

        print("=== document.title ===")
        print(page.title())

        print("\n=== visible body text (first 4000 chars) ===")
        body_text = page.inner_text("body")
        print(body_text[:4000])

        print(f"\n=== full body text length: {len(body_text)} ===")

        browser.close()

    print("\n=== searching main-DLXMVjOc.js for date/time-shaped literals ===")
    r = requests.get("https://localtenniscourts.com/assets/main-DLXMVjOc.js", headers=HEADERS, timeout=20)
    text = r.text
    for pattern, label in [
        (r"202[5-9]-[01]\d-[0-3]\d", "ISO date"),
        (r"\b[0-2]\d:[0-5]\d\b", "HH:MM time"),
        (r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", "day name"),
        (r"\bhighbury\b", "highbury (case-insens via lower)"),
    ]:
        matches = re.findall(pattern, text, re.IGNORECASE if "highbury" in label else 0)
        print(f"{label}: {len(matches)} match(es)", matches[:10])

    return 0


if __name__ == "__main__":
    sys.exit(main())
