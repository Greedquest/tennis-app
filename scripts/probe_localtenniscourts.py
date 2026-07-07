#!/usr/bin/env python3
"""Throwaway probe: discover how localtenniscourts.com sources its data.

This is NOT part of the app — it's a one-shot reconnaissance script meant to
run somewhere with real internet egress (GitHub Actions), because the dev
sandbox's outbound proxy blocks this domain outright (CONNECT rejected at the
proxy, before it even reaches the site). See the "probe on GitHub Actions"
gotcha in CLAUDE.md for the general pattern this follows.

Round 2: the first pass showed the page is fully server-rendered (no JSON
XHR at all — only analytics beacons) and found exactly one data table. This
round answers the open question that matters for the real implementation:
does the "q=highbury-fields,islington-tennis-centre-outdoor" query merge
both venues into one combined court-count table, or is it actually only
resolving to a single venue? We answer this by loading the combined query
and each single-venue query separately and comparing the per-slot counts,
plus grepping the rendered text for venue name mentions and any filter
controls that reveal venue identifiers/labels.

Delete this script (and its throwaway workflow) once the answer is known
and the real fetch/parse code is written against it.
"""

import json
import re
import sys

from playwright.sync_api import sync_playwright

BASE = "https://localtenniscourts.com/"
QUERIES = {
    "combined": "highbury-fields,islington-tennis-centre-outdoor",
    "highbury_only": "highbury-fields",
    "itc_outdoor_only": "islington-tennis-centre-outdoor",
}


def extract_tables(page):
    return page.evaluate(
        """
        () => {
            function cellSummary(cell) {
                const txt = cell.innerText.trim().replace(/\\s+/g, ' ');
                const bg = cell.className.includes('emerald') ? 'FREE'
                         : cell.className.includes('red') ? 'BOOKED'
                         : '?';
                return `${txt || '-'}[${bg}]`;
            }
            const tables = Array.from(document.querySelectorAll('table'));
            const headerTable = tables.find(t => t.querySelectorAll('thead th').length > 1);
            const dataTable = tables.find(t => t.querySelectorAll('tbody tr').length > 0);
            const dateHeaders = headerTable
                ? Array.from(headerTable.querySelectorAll('thead th')).map(th => th.innerText.trim())
                : [];
            const rows = dataTable
                ? Array.from(dataTable.querySelectorAll('tbody tr')).map(tr =>
                    Array.from(tr.querySelectorAll('td')).map(cellSummary)
                  )
                : [];
            return { dateHeaders, rows, tableCount: tables.length };
        }
        """
    )


def find_venue_controls(page):
    return page.evaluate(
        """
        () => {
            const candidates = Array.from(
                document.querySelectorAll('[data-value], input[type=checkbox], label, [role=checkbox]')
            );
            return candidates
                .map(el => ({
                    tag: el.tagName,
                    text: (el.innerText || '').trim().slice(0, 60),
                    dataValue: el.getAttribute('data-value'),
                    value: el.getAttribute('value'),
                    checked: el.checked !== undefined ? el.checked : null,
                }))
                .filter(x => x.text || x.dataValue || x.value);
        }
        """
    )


def load_and_summarize(p, query_label, q):
    url = f"{BASE}?q={q.replace(',', '%2C')}"
    browser = p.chromium.launch()
    page = browser.new_page()
    print(f"\nNavigating [{query_label}] {url}", file=sys.stderr)
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)

    tables = extract_tables(page)
    body_text = page.inner_text("body")

    mentions = {}
    for name in ("Highbury", "Islington", "ITC"):
        idxs = [m.start() for m in re.finditer(name, body_text)]
        mentions[name] = [body_text[max(0, i - 40) : i + 40].replace("\n", " ") for i in idxs[:3]]

    controls = find_venue_controls(page) if query_label == "combined" else None

    browser.close()
    return {"tables": tables, "mentions": mentions, "controls": controls}


def main() -> int:
    results = {}
    with sync_playwright() as p:
        for label, q in QUERIES.items():
            results[label] = load_and_summarize(p, label, q)

    for label, result in results.items():
        print(f"\n=== [{label}] tableCount={result['tables']['tableCount']} ===")
        print("date headers:", result["tables"]["dateHeaders"])
        for row in result["tables"]["rows"]:
            print(" ", row)
        print("mentions:", json.dumps(result["mentions"], indent=2))
        if result["controls"] is not None:
            print("venue controls:", json.dumps(result["controls"], indent=2)[:3000])

    return 0


if __name__ == "__main__":
    sys.exit(main())
