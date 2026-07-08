#!/usr/bin/env python3
"""Probe localtenniscourts.com to find how it serves court-availability data.

Throwaway diagnostic tool, same rationale as scripts/probe_venue.py: the
sandbox this agent runs in can't reach the public internet, so this has to be
run somewhere with real egress (a GitHub Actions job) and the output read
back from the job logs.

What it does, cheapest check first:
  1. Fetch the page HTML directly (no JS execution) and look for:
     - a JSON data island (Next.js __NEXT_DATA__, Nuxt __NUXT__,
       window.__INITIAL_STATE__, or similar embedded state blobs)
     - any inline/linked script referencing "/api/" or similar paths
     - <table>/<tr> markup that suggests the slot grid is server-rendered
  2. If nothing conclusive, render with Playwright (headless Chromium),
     capture every network request the page fires, and dump the URL +
     content-type + a truncated body for anything that looks like JSON.

Usage:
    python scripts/probe_ltc.py
    python scripts/probe_ltc.py --url "https://localtenniscourts.com/?q=highbury-fields,islington-tennis-centre-outdoor"
"""

import argparse
import json
import re
import sys

import requests

DEFAULT_URL = "https://localtenniscourts.com/?q=highbury-fields,islington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

DATA_ISLAND_PATTERNS = [
    r"__NEXT_DATA__",
    r"__NUXT__",
    r"window\.__INITIAL_STATE__",
    r"window\.__PRELOADED_STATE__",
    r"<script[^>]+type=[\"']application/json[\"']",
]


def fetch_html(url: str) -> tuple[int, str, dict]:
    r = requests.get(url, headers=HEADERS, timeout=20)
    return r.status_code, r.text, dict(r.headers)


def static_probe(url: str) -> None:
    print(f"=== Static fetch: {url} ===")
    status, html, headers = fetch_html(url)
    print(f"status={status} content-type={headers.get('content-type')} bytes={len(html)}")
    print(f"server={headers.get('server')!r} x-powered-by={headers.get('x-powered-by')!r}")

    for pat in DATA_ISLAND_PATTERNS:
        hits = re.findall(pat, html)
        if hits:
            print(f"MATCH data-island pattern {pat!r}: {len(hits)} occurrence(s)")

    api_paths = sorted(set(re.findall(r"""["'](/[a-zA-Z0-9_\-./]*api[a-zA-Z0-9_\-./]*)["']""", html)))
    if api_paths:
        print(f"Found {len(api_paths)} path(s) containing 'api':")
        for p in api_paths[:40]:
            print(f"  {p}")

    scripts = sorted(set(re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)))
    print(f"\n{len(scripts)} external <script src> reference(s):")
    for s in scripts[:40]:
        print(f"  {s}")

    n_tables = len(re.findall(r"<table", html, flags=re.I))
    n_rows = len(re.findall(r"<tr", html, flags=re.I))
    print(f"\n<table> tags: {n_tables}, <tr> tags: {n_rows}")

    # Dump a chunk of the raw HTML for manual inspection in the job log.
    print("\n--- first 3000 chars of HTML ---")
    print(html[:3000])
    print("--- last 1500 chars of HTML ---")
    print(html[-1500:])


def dynamic_probe(url: str) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\nplaywright not installed; skipping dynamic (network-capture) probe.")
        return

    print(f"\n=== Dynamic fetch (Playwright) with network capture: {url} ===")
    requests_seen: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=HEADERS["User-Agent"])

        def on_response(response):
            ct = response.headers.get("content-type", "")
            entry = {
                "url": response.url,
                "status": response.status,
                "content_type": ct,
            }
            if "json" in ct:
                try:
                    body = response.text()
                    entry["body_snippet"] = body[:1500]
                except Exception as e:  # noqa: BLE001
                    entry["body_error"] = str(e)
            requests_seen.append(entry)

        page.on("response", on_response)
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        # Grab whatever slot/day/table structure ends up in the DOM too.
        body_text = page.inner_text("body")[:3000]
        browser.close()

    print(f"\nCaptured {len(requests_seen)} network responses.")
    json_like = [r for r in requests_seen if "json" in r.get("content_type", "")]
    print(f"{len(json_like)} looked like JSON:")
    for r in json_like:
        print(json.dumps(r, indent=2)[:2000])

    non_asset = [
        r
        for r in requests_seen
        if not re.search(r"\.(png|jpg|jpeg|svg|css|woff2?|ico)(\?|$)", r["url"])
    ]
    print(f"\n{len(non_asset)} non-asset response URLs:")
    for r in non_asset:
        print(f"  {r['status']:4} {r['content_type']:30} {r['url']}")

    print("\n--- rendered <body> innerText (first 3000 chars) ---")
    print(body_text)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Probe localtenniscourts.com for its data source.")
    p.add_argument("--url", default=DEFAULT_URL, help="Page URL to probe.")
    args = p.parse_args(argv)

    static_probe(args.url)
    dynamic_probe(args.url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
