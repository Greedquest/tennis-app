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


def dump_network_and_html(page, label):
    html = page.content()
    print(f"--- [{label}] URL ---")
    print(page.url)
    print(f"--- [{label}] TITLE ---")
    print(page.title())
    print(f"--- [{label}] HTML LENGTH --- {len(html)}")
    print(f"--- [{label}] FULL HTML ---")
    print(html)

    # links that might lead to a per-venue timetable page
    hrefs = sorted(set(re.findall(r'href="([^"]+)"', html)))
    print(f"--- [{label}] LINKS ({len(hrefs)}) ---")
    for h in hrefs:
        print(h)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        seen = []

        def on_response(response):
            req = response.request
            ctype = response.headers.get("content-type", "")
            interesting = req.resource_type in ("xhr", "fetch") or "json" in ctype
            if interesting:
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
                seen.append(entry)
                print("NETWORK:", json.dumps(entry)[:2500])

        page.on("response", on_response)
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        dump_network_and_html(page, "landing")

        # Try to find and click a link/card leading to an actual venue
        # timetable (heuristics: hrefs containing 'venue' or the slugs
        # themselves, or clickable cards containing the venue names).
        candidates = page.locator(
            "a[href*='highbury'], a[href*='islington'], a[href*='venue'], a[href*='court']"
        )
        count = candidates.count()
        print(f"--- CANDIDATE VENUE LINKS: {count} ---")
        for i in range(min(count, 5)):
            try:
                print(candidates.nth(i).get_attribute("href"))
            except Exception as e:  # noqa: BLE001
                print("err reading href:", e)

        if count > 0:
            seen.clear()
            href = candidates.first.get_attribute("href")
            print(f"--- NAVIGATING TO FIRST CANDIDATE: {href} ---")
            candidates.first.click()
            page.wait_for_timeout(2000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception as e:  # noqa: BLE001
                print("networkidle wait failed:", e)
            page.wait_for_timeout(2000)
            dump_network_and_html(page, "venue-page")

        browser.close()


if __name__ == "__main__":
    main()
