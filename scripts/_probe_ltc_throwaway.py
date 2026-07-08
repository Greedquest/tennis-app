#!/usr/bin/env python3
"""THROWAWAY probe v3: find localtenniscourts.com's underlying API.

The site is a client-rendered SPA (Vite bundle). Its first load showed an
error ("problem loading the court availability data"), so this probe:
  1. Logs requestfailed events (why did the fetch die?).
  2. Retries the page load once.
  3. Downloads the JS bundles directly and greps them for API endpoint
     strings (works even if the live fetch never succeeds in headless CI).
"""

import json
import re

import requests
from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"
BUNDLES = [
    "https://localtenniscourts.com/assets/main-DLXMVjOc.js",
    "https://localtenniscourts.com/assets/index-Bf7utVcV.js",
]


def probe_bundles():
    print("=== STATIC BUNDLE ANALYSIS ===")
    for url in BUNDLES:
        try:
            r = requests.get(url, timeout=20)
            body = r.text
            print(f"--- {url} ({len(body)} bytes, status {r.status_code}) ---")
            # Look for absolute https URLs (candidate API hosts)
            urls = sorted(set(re.findall(r'https?://[a-zA-Z0-9_\-./%]+', body)))
            api_like = [u for u in urls if not any(
                skip in u for skip in ("googletagmanager", "google-analytics", "cloudflareinsights",
                                        "buymeacoffee", "w3.org", "fonts.")
            )]
            print(f"non-analytics URLs found ({len(api_like)}):")
            for u in api_like:
                print(" ", u)
            # Look for relative /api/... paths
            rel_api = sorted(set(re.findall(r'["\'](/api/[a-zA-Z0-9_\-./{}]*)["\']', body)))
            if rel_api:
                print("relative /api/ paths:")
                for u in rel_api:
                    print(" ", u)
            # Look for supabase/firebase/etc project refs
            for kw in ("supabase", "firebaseio", "vercel.app", "functions", "workers.dev", "better-admin", "bookings.better"):
                hits = sorted(set(re.findall(rf'[^"\']*{kw}[^"\']*', body)))
                if hits:
                    print(f"keyword '{kw}' hits ({len(hits)}):")
                    for h in hits[:10]:
                        print("  ", h[:200])
        except Exception as e:  # noqa: BLE001
            print(f"--- {url} FAILED: {e} ---")


def probe_live():
    print("=== LIVE PAGE PROBE ===")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_request_failed(req):
            print(f"REQUEST FAILED: {req.method} {req.url} -> {req.failure}")

        def on_response(response):
            req = response.request
            ctype = response.headers.get("content-type", "")
            if req.resource_type in ("xhr", "fetch") or "json" in ctype:
                entry = {
                    "url": response.url,
                    "method": req.method,
                    "status": response.status,
                    "resource_type": req.resource_type,
                    "content_type": ctype,
                }
                if "json" in ctype:
                    try:
                        entry["body_preview"] = json.dumps(response.json())[:4000]
                    except Exception as e:  # noqa: BLE001
                        entry["body_error"] = str(e)
                print("NETWORK:", json.dumps(entry)[:2500])

        page.on("requestfailed", on_request_failed)
        page.on("response", on_response)

        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        print("--- after first load, body snippet ---")
        html = page.content()
        if "problem loading" in html:
            print("ERROR STATE detected, reloading once...")
            page.reload(wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(4000)
            html = page.content()
            print("ERROR STATE after reload?", "problem loading" in html)

        m = re.search(r'<main[^>]*>(.*?)</main>', html, re.S)
        if m:
            print("--- MAIN CONTENT (post-reload) ---")
            print(m.group(1)[:6000])

        browser.close()


def main() -> None:
    probe_bundles()
    probe_live()


if __name__ == "__main__":
    main()
