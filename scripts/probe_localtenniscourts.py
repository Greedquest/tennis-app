#!/usr/bin/env python3
"""Throwaway probe: inspect localtenniscourts.com's availability table structure.

Prior sessions disagreed on two points and this probe re-checks both from a
runner with real network access (this sandbox's proxy 403s the site):

  1. Does the combined query (`?q=highbury-fields,islington-tennis-centre-
     outdoor`) return ONE merged table, or does each venue get its own
     column/table? The brief wants us to confirm court identity, i.e. that
     we can tell Highbury Fields slots apart from Islington Tennis Centre
     outdoor slots.
  2. Is there a JSON API (check response headers / any `/api/` or `.json`
     requests implied by the HTML), or is it plain server-rendered HTML
     fetchable via a single `requests.get` (no browser needed)?

Delete this file (and its throwaway workflow) once the findings are copied
into CLAUDE.md / the real implementation.
"""

import json
import re
import sys

import requests
from bs4 import BeautifulSoup

COMBINED_URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"
SINGLE_URLS = {
    "highbury-fields": "https://localtenniscourts.com/?q=highbury-fields",
    "islington-tennis-centre-outdoor": "https://localtenniscourts.com/?q=islington-tennis-centre-outdoor",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def describe(label: str, url: str) -> None:
    print(f"\n=== {label}: {url} ===")
    r = requests.get(url, headers=HEADERS, timeout=20)
    print(f"status={r.status_code} content-type={r.headers.get('content-type')} bytes={len(r.content)}")
    if not r.ok:
        print(f"body (first 500 chars): {r.text[:500]!r}")
        return

    text = r.text
    # Look for evidence of an underlying JSON/XHR API referenced in the HTML/JS.
    api_hits = sorted(set(re.findall(r'"(/api/[^"]+|https?://[^"]*api[^"]*)"', text)))[:20]
    print(f"possible API refs found in HTML: {api_hits}")

    soup = BeautifulSoup(text, "html.parser")
    tables = soup.find_all("table")
    print(f"n_tables={len(tables)}")
    for i, t in enumerate(tables):
        thead_ths = [th.get_text(strip=True) for th in t.select("thead th")]
        first_rows = t.select("tbody tr")[:3]
        print(f"  table[{i}] thead={thead_ths}")
        for r_i, row in enumerate(first_rows):
            cells = row.find_all(["td", "th"])
            cell_info = [
                {"text": c.get_text(strip=True), "class": c.get("class")} for c in cells
            ]
            print(f"    row[{r_i}] = {json.dumps(cell_info)}")

    # Any headings/labels that name a specific venue (helps confirm which
    # venue a column belongs to when there are multiple).
    venue_labels = sorted(
        set(
            el.get_text(strip=True)
            for el in soup.find_all(["h1", "h2", "h3", "caption"])
            if el.get_text(strip=True)
        )
    )
    print(f"headings/captions: {venue_labels}")


def main() -> int:
    describe("combined", COMBINED_URL)
    for label, url in SINGLE_URLS.items():
        describe(label, url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
