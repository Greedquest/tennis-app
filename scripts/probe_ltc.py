#!/usr/bin/env python3
"""Throwaway probe #3: this is a TanStack Start SSR app (streamed HTML).
Data is likely embedded in the streamed response itself rather than fetched
client-side from a separate API. Dump the FULL html and search for
court/availability-looking payloads anywhere in it, plus try the site's own
data endpoints TanStack Start typically exposes.
"""

import re
import sys

import requests

BASE = "https://localtenniscourts.com"
QS = "?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def main():
    s = requests.Session()
    r = s.get(BASE + "/" + QS, headers=HEADERS, timeout=30)
    html = r.text
    print(f"Total length: {len(html)}")

    print("\n--- all <script> tag openings (first 200 chars of body if inline) ---")
    for m in re.finditer(r"<script([^>]*)>(.*?)</script>", html, re.S | re.I):
        attrs, body = m.group(1), m.group(2)
        if body.strip():
            print(f"attrs={attrs!r} bodylen={len(body)}")
            print(body[:300])
            print("...")
    print("\n--- keyword search across full html: starts_at / spaces / Wednesday / Highbury / Islington / court / __TSR ---")
    for kw in ["starts_at", "spaces", "Wednesday", "Highbury", "Islington", "court", "__TSR", "dehydrat", "hydrat", "loaderData", "RouterProvider", "streamedValue"]:
        idxs = [m.start() for m in re.finditer(re.escape(kw), html, re.I)]
        print(f"{kw!r}: {len(idxs)} occurrences" + (f" first at {idxs[0]}" if idxs else ""))
        if idxs:
            i = idxs[0]
            print("   context:", html[max(0, i - 150):i + 150].replace("\n", " "))

    print("\n--- last 3000 chars of html (streamed tail often has the payload) ---")
    print(html[-3000:])

    # TanStack Start server-fn / loader convention checks
    guesses = [
        "_serverFn",
        "api/trpc",
        "__data.json" + QS,
    ]
    print("\n--- probing TanStack-ish endpoints ---")
    for g in guesses:
        try:
            gr = s.get(BASE + "/" + g, headers=HEADERS, timeout=15)
            print(f"{gr.status_code:4}  {gr.headers.get('content-type', ''):30}  {BASE}/{g}  ({len(gr.content)} bytes)")
        except Exception as e:
            print(f" ERR  {BASE}/{g}  {e}")


if __name__ == "__main__":
    sys.exit(main() or 0)
