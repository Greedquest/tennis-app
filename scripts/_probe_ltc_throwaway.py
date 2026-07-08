#!/usr/bin/env python3
"""THROWAWAY probe: inspect localtenniscourts.com for a JSON API.

Not part of the app. Run once from a GitHub Actions job (real internet
egress) to discover whether the page is backed by an XHR/fetch JSON API,
then delete this file and its workflow. See CLAUDE.md gotchas for why this
can't be done from the sandbox directly.
"""

import json
import re

from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        seen = []

        def on_response(response):
            req = response.request
            if req.resource_type in ("xhr", "fetch"):
                ctype = response.headers.get("content-type", "")
                entry = {
                    "url": response.url,
                    "method": req.method,
                    "status": response.status,
                    "content_type": ctype,
                }
                if "json" in ctype:
                    try:
                        entry["body_preview"] = json.dumps(response.json())[:4000]
                    except Exception as e:  # noqa: BLE001
                        entry["body_error"] = str(e)
                seen.append(entry)
                print("NETWORK:", json.dumps(entry)[:2500])

        page.on("response", on_response)
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        print("--- PAGE TITLE ---")
        print(page.title())

        html = page.content()
        print("--- HTML LENGTH ---", len(html))

        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if m:
            print("--- __NEXT_DATA__ ---")
            print(m.group(1)[:6000])

        # Fallback: any inline <script> blob mentioning "slot", "court", or "available"
        for i, block in enumerate(re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)):
            if re.search(r"slot|court|available|booking", block, re.I) and len(block) > 200:
                print(f"--- INLINE SCRIPT #{i} (matched keywords) ---")
                print(block[:3000])

        print("--- ALL XHR/FETCH SUMMARY ---")
        print(json.dumps(seen, indent=2)[:10000])

        browser.close()


if __name__ == "__main__":
    main()
