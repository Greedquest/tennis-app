#!/usr/bin/env python3
"""Throwaway probe: inspect localtenniscourts.com for a JSON API vs HTML-only.

Run only from an environment with real internet egress (GitHub Actions),
never from the agent sandbox (proxy 403s this host). Deleted after use.
"""

import json
import re
import sys

import requests

BASE = "https://localtenniscourts.com/"
QS = "?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def dump_response(label, r):
    print(f"\n=== {label} ===")
    print(f"URL: {r.url}")
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type')}")
    print(f"Content-Length: {len(r.content)}")
    print("Headers:", dict(r.headers))


def main():
    s = requests.Session()

    r = s.get(BASE + QS, headers=HEADERS, timeout=20)
    dump_response("Main page", r)
    html = r.text

    print("\n--- First 3000 chars of HTML ---")
    print(html[:3000])

    print("\n--- script src attributes ---")
    for m in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html):
        print(m)

    print("\n--- inline script snippets mentioning api/json/fetch/axios ---")
    for m in re.finditer(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", html, re.S | re.I):
        body = m.group(1)
        if re.search(r"api|fetch\(|axios|XMLHttpRequest|__NEXT_DATA__|window\.__", body, re.I):
            print(body[:2000])
            print("---")

    print("\n--- any embedded JSON-looking blobs (window.X = {...}) ---")
    for m in re.finditer(r"window\.(\w+)\s*=\s*(\{.*?\}|\[.*?\]);", html, re.S):
        name, blob = m.group(1), m.group(2)
        print(f"window.{name} = <{len(blob)} chars>")
        try:
            parsed = json.loads(blob)
            print(json.dumps(parsed, indent=2)[:1500])
        except Exception as e:
            print(f"  (not parseable: {e})")

    print("\n--- links referencing /api/, .json, wp-json ---")
    for m in re.findall(r'["\'](/[^"\']*(?:api|\.json|wp-json)[^"\']*)["\']', html, re.I):
        print(m)

    # Try a handful of common API-ish paths directly.
    guesses = [
        "api/availability",
        "api/courts",
        "api/search",
        "wp-json/",
        "wp-json/wp/v2",
        "_next/data",
    ]
    print("\n--- probing guessed endpoints ---")
    for g in guesses:
        try:
            gr = s.get(BASE + g, headers=HEADERS, timeout=15)
            print(f"{gr.status_code:4}  {gr.headers.get('content-type', ''):30}  {BASE}{g}  ({len(gr.content)} bytes)")
        except Exception as e:
            print(f" ERR  {BASE}{g}  {e}")


if __name__ == "__main__":
    sys.exit(main() or 0)
