#!/usr/bin/env python3
"""Throwaway probe: does a plain HTTP GET (no JS execution) return the
populated availability table, or does the table only appear after client-side
JS runs?

This decides the real implementation's dependency footprint: if the SSR'd
HTML already contains the table, a Termux/cron script can use `requests` +
an HTML parser with zero browser dependency (important — Playwright/Chromium
is a poor fit for Android Termux). If not, we're stuck needing a headless
browser everywhere this runs.

Delete this script (and its throwaway workflow) once this is answered and
the real implementation is written.
"""

import re
import sys

import requests

URL = "https://localtenniscourts.com/?q=highbury-fields"


def main() -> int:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    r = requests.get(URL, headers=headers, timeout=15)
    print(f"status={r.status_code} content-length={len(r.text)}")

    html = r.text
    has_time_slot = "08:00" in html or "19:00" in html
    has_court_word = "court" in html.lower()
    has_emerald = "emerald" in html
    has_wed_header = re.search(r"Wed \d\d", html) is not None

    print(f"contains '08:00' or '19:00': {has_time_slot}")
    print(f"contains 'court': {has_court_word}")
    print(f"contains 'emerald' (free-slot class): {has_emerald}")
    print(f"contains 'Wed NN' date header: {has_wed_header}")

    idx = html.find("19:00")
    if idx != -1:
        print("\n--- context around first '19:00' ---")
        print(html[max(0, idx - 300) : idx + 800])
    else:
        idx = html.find("08:00")
        if idx != -1:
            print("\n--- context around first '08:00' ---")
            print(html[max(0, idx - 300) : idx + 800])
        else:
            print("\n--- no time slot found; first 2000 chars of <body> ---")
            body_start = html.find("<body")
            print(html[body_start : body_start + 2000])

    return 0


if __name__ == "__main__":
    sys.exit(main())
