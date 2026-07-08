#!/usr/bin/env python3
"""One-off probe: does localtenniscourts.com expose a JSON API?

Fetches the page HTML plus any same-origin script bundles it references and
greps them for fetch/XHR/API endpoint patterns. Run from an environment with
real internet egress (the dev sandbox's proxy 403s this domain) — see
CLAUDE.md gotchas. Throwaway diagnostic script; delete after use.
"""

import re
import sys
from urllib.parse import urljoin

import requests

BASE = "https://localtenniscourts.com/"
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

ENDPOINT_RE = re.compile(
    r"""["'](?:https?://[^"']+)?/(?:api|wp-json|graphql|data|_next/data)[^"'\s]*["']|"""
    r"""fetch\(\s*["'][^"')]+["']|"""
    r"""\.json["']""",
    re.IGNORECASE,
)
SCRIPT_SRC_RE = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def probe_url(url: str, label: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"\n=== {label}: {url} ===")
        print(f"status={r.status_code} bytes={len(r.content)}")
        return r.text if r.ok else ""
    except Exception as e:  # noqa: BLE001
        print(f"\n=== {label}: {url} ===\nERROR: {e}")
        return ""


def main() -> int:
    html = probe_url(PAGE, "page")
    if not html:
        print("Could not fetch page; aborting.")
        return 1

    print("\n--- inline endpoint-like matches on page ---")
    matches = sorted(set(ENDPOINT_RE.findall(html)))
    for m in matches[:50]:
        print(m)
    if not matches:
        print("(none found)")

    scripts = sorted(set(SCRIPT_SRC_RE.findall(html)))
    print(f"\n--- {len(scripts)} script src(s) found ---")
    for s in scripts:
        print(s)

    for s in scripts:
        script_url = urljoin(BASE, s)
        js = probe_url(script_url, "script")
        if not js:
            continue
        js_matches = sorted(set(ENDPOINT_RE.findall(js)))
        print(f"--- endpoint-like matches in {script_url} ---")
        for m in js_matches[:50]:
            print(m)
        if not js_matches:
            print("(none found)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
