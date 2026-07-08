#!/usr/bin/env python3
"""Throwaway probe #2: it's a client-rendered SPA (Vite bundle) -- inspect the
JS assets themselves for API endpoint URLs, since the initial HTML has none.
"""

import re
import sys

import requests

BASE = "https://localtenniscourts.com"
ASSETS = [
    "/assets/main-DLXMVjOc.js",
    "/assets/index-Bf7utVcV.js",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

URL_RE = re.compile(r'https?://[A-Za-z0-9_\-.]+(?:/[A-Za-z0-9_\-./%?=&{}]*)?')


def main():
    s = requests.Session()
    for path in ASSETS:
        r = s.get(BASE + path, headers=HEADERS, timeout=30)
        print(f"\n=== {path} ({r.status_code}, {len(r.content)} bytes) ===")
        if not r.ok:
            continue
        js = r.text

        urls = sorted(set(URL_RE.findall(js)))
        print(f"--- {len(urls)} unique absolute URLs found ---")
        for u in urls:
            print(u)

        print("--- lines mentioning supabase/xano/firebase/api. ---")
        for m in re.finditer(r".{80}(supabase|xano|firebase|/api/|better-admin|bookings\.better).{80}", js, re.I):
            print(m.group(0))
            print("---")

        print("--- relative fetch()/axios path literals ---")
        for m in re.findall(r'(?:fetch|axios\.\w+)\(\s*[`"\']([^`"\']+)[`"\']', js):
            print(m)


if __name__ == "__main__":
    sys.exit(main() or 0)
