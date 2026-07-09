#!/usr/bin/env python3
"""Throwaway probe: inspect localtenniscourts.com's JS bundles for the real API.

Not meant to be kept in the repo -- run once on a GitHub Actions runner (real
egress), read the logs, then delete this file + its workflow.
"""

import re
import sys

import requests

BASE = "https://localtenniscourts.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

BUNDLES = [
    "/assets/main-DLXMVjOc.js",
    "/assets/index-Bf7utVcV.js",
]

# Patterns that usually reveal a backend: absolute URLs, relative /api paths,
# common BaaS hostnames, and fetch/axios call sites.
URL_RE = re.compile(r"https?://[A-Za-z0-9_.\-]+(?:/[^\s\"'`)]*)?")
REL_API_RE = re.compile(r"[\"'`](/[a-zA-Z0-9_\-./]*(?:api|court|venue|slot|avail)[a-zA-Z0-9_\-./]*)[\"'`]")
FETCH_RE = re.compile(r"(fetch|axios\.(?:get|post)|\.get\(|\.post\()\s*\(\s*[\"'`]([^\"'`]+)")


def main() -> int:
    for path in BUNDLES:
        url = BASE + path
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
        except Exception as e:
            print(f"\n=== {url} -> ERROR {e} ===")
            continue

        print(f"\n=== {url} ===")
        print("status:", r.status_code, "len:", len(r.content))
        if not r.ok:
            continue

        text = r.text

        urls = sorted(set(URL_RE.findall(text)))
        interesting = [
            u
            for u in urls
            if not any(
                skip in u
                for skip in (
                    "w3.org",
                    "googletagmanager",
                    "google-analytics",
                    "buymeacoffee",
                    "cloudflare",
                    "fonts.googleapis",
                    "fonts.gstatic",
                    "schema.org",
                )
            )
        ]
        print(f"\n--- {len(interesting)} interesting absolute URL(s) (of {len(urls)} total) ---")
        for u in interesting[:200]:
            print(u)

        rel_apis = sorted(set(REL_API_RE.findall(text)))
        print(f"\n--- {len(rel_apis)} relative api/court/venue/slot/avail path(s) ---")
        for p in rel_apis[:200]:
            print(p)

        fetch_calls = FETCH_RE.findall(text)
        print(f"\n--- {len(fetch_calls)} fetch/axios call site(s) ---")
        for kind, target in fetch_calls[:200]:
            print(f"{kind} -> {target}")

        for marker in ("supabase", "firebaseio", "firestore", "vercel.app", "workers.dev", "amazonaws", "pocketbase"):
            if marker in text:
                print(f"\nFound backend marker: {marker}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
