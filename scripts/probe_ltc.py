#!/usr/bin/env python3
"""One-off probe: how does localtenniscourts.com structure its court table?

Round 2: no client-side JSON API was found (round 1), so the data must be
server-rendered directly into the HTML. This dumps the table-ish markup so we
can write an HTML parser against real structure instead of guessing.
Run from an environment with real internet egress (the dev sandbox's proxy
403s this domain) — see CLAUDE.md gotchas. Throwaway diagnostic; delete after use.
"""

import re
import sys

import requests

PAGE = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def strip_scripts(html: str) -> str:
    return re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)


def main() -> int:
    r = requests.get(PAGE, headers=HEADERS, timeout=20)
    print(f"status={r.status_code} bytes={len(r.content)}")
    if not r.ok:
        return 1

    html = r.text
    body_start = html.lower().find("<body")
    body = html[body_start:] if body_start != -1 else html
    body = strip_scripts(body)

    print("\n=== FULL BODY (scripts stripped) ===\n")
    print(body)

    return 0


if __name__ == "__main__":
    sys.exit(main())
