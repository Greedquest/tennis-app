#!/usr/bin/env python3
"""Throwaway probe, round 4: look for SSR-hydrated data inline in the HTML.

Findings so far:
  - Round 1 (Playwright, full network capture): no XHR/fetch call carries
    court data — only HTML shell, 2 JS bundles, 1 CSS, analytics/widget noise.
  - Round 3 (JS bundle grep): the UI code references `cellData.spaces` and
    `cellData.day` (e.g. `${o.day} @ ${a}`) — so the client expects a
    pre-built `{day, spaces: [...]}` structure per cell. No literal API base
    URL string appears in either bundle.
  - This app is built with TanStack Router/Start (visible from bundle
    strings), which supports SSR route loaders that dehydrate fetched data
    into an inline <script> in the HTML response, not a client-side XHR.
    That would explain both findings at once.

This probe fetches the raw HTML via plain requests (no browser needed — we
want the pre-hydration payload, not post-JS DOM) and dumps every inline
<script>...</script> body, plus greps the whole document for "spaces"/"day"
tokens, so we can find the embedded payload if there is one.
"""

import re
import sys

import requests

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

INLINE_SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.I | re.S)


def main() -> int:
    print(f"GET {URL}")
    r = requests.get(URL, headers=HEADERS, timeout=20)
    html = r.text
    print(f"status={r.status_code} length={len(html)}")

    scripts = INLINE_SCRIPT_RE.findall(html)
    print(f"\n=== {len(scripts)} inline <script> block(s) ===")
    for i, s in enumerate(scripts):
        s = s.strip()
        print(f"\n--- inline script #{i} (len={len(s)}) ---")
        print(s[:4000])

    print("\n=== whole-document occurrences of 'spaces' ===")
    for m in re.finditer("spaces", html):
        start = max(0, m.start() - 200)
        end = min(len(html), m.start() + 200)
        print(f"...{html[start:end]}...\n")

    print("\n=== whole-document occurrences of '\"day\"' ===")
    for m in re.finditer(r'"day"', html):
        start = max(0, m.start() - 200)
        end = min(len(html), m.start() + 200)
        print(f"...{html[start:end]}...\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
