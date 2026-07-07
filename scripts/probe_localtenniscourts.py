#!/usr/bin/env python3
"""Throwaway probe: discover how localtenniscourts.com sources its data.

This is NOT part of the app — it's a one-shot reconnaissance script meant to
run somewhere with real internet egress (GitHub Actions), because the dev
sandbox's outbound proxy blocks this domain outright (CONNECT rejected at the
proxy, before it even reaches the site). See the "probe on GitHub Actions"
gotcha in CLAUDE.md for the general pattern this follows.

It loads the page in headless Chromium via Playwright, records every
network request/response the page makes while rendering, and prints:
  - every XHR/fetch request URL, method, and status
  - the body of any JSON responses (so we can see the data shape)
  - a snippet of the final rendered HTML (fallback if there's no JSON API)

Delete this script (and its throwaway workflow) once the API shape is known
and the real fetch/parse code is written against it.
"""

import json
import sys

from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"


def main() -> int:
    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_response(response):
            request = response.request
            if request.resource_type not in ("xhr", "fetch", "document"):
                return
            entry = {
                "url": response.url,
                "method": request.method,
                "status": response.status,
                "resource_type": request.resource_type,
                "content_type": response.headers.get("content-type", ""),
            }
            if "json" in entry["content_type"]:
                try:
                    entry["body"] = response.json()
                except Exception as e:  # noqa: BLE001 - diagnostic tool
                    entry["body_error"] = str(e)
            captured.append(entry)

        page.on("response", on_response)

        print(f"Navigating to {URL}", file=sys.stderr)
        page.goto(URL, wait_until="networkidle", timeout=30000)
        # Give any deferred/polling XHR a moment to fire after networkidle.
        page.wait_for_timeout(3000)

        html = page.content()
        title = page.title()

        # Structurally extract every <table> on the page: headers, and each
        # cell's text/class/title/aria-label (status is almost certainly
        # conveyed via a color class or icon, not plain text).
        tables = page.evaluate(
            """
            () => {
                function describeCell(cell) {
                    return {
                        text: cell.innerText.trim(),
                        class: cell.className,
                        title: cell.getAttribute('title'),
                        ariaLabel: cell.getAttribute('aria-label'),
                        html: cell.innerHTML.slice(0, 300),
                    };
                }
                return Array.from(document.querySelectorAll('table')).map((table) => {
                    // Try to find a heading/caption near this table for venue context.
                    let heading = null;
                    let el = table.closest('div');
                    for (let hops = 0; el && hops < 6 && !heading; hops++, el = el.parentElement) {
                        const h = el.querySelector('h1, h2, h3, h4, caption');
                        if (h) heading = h.innerText.trim();
                    }
                    const headerCells = Array.from(table.querySelectorAll('thead th')).map(describeCell);
                    const rows = Array.from(table.querySelectorAll('tbody tr')).map((tr) =>
                        Array.from(tr.querySelectorAll('td')).map(describeCell)
                    );
                    return { heading, headerCells, rows };
                });
            }
            """
        )

        browser.close()

    print("\n=== PAGE TITLE ===")
    print(title)

    print("\n=== CAPTURED REQUESTS ===")
    for entry in captured:
        body_note = ""
        if "body" in entry:
            body_note = f"  body={json.dumps(entry['body'])[:2000]}"
        elif "body_error" in entry:
            body_note = f"  body_error={entry['body_error']}"
        print(
            f"{entry['status']:>4} {entry['method']:<5} [{entry['resource_type']:<8}] "
            f"{entry['url']}{body_note}"
        )

    print("\n=== RENDERED HTML LENGTH ===")
    print(len(html))

    print("\n=== STRUCTURED TABLES ===")
    print(json.dumps(tables, indent=2)[:20000])

    return 0


if __name__ == "__main__":
    sys.exit(main())
