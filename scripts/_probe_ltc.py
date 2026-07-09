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

SEED_BUNDLES = [
    "/assets/main-DLXMVjOc.js",
    "/assets/index-Bf7utVcV.js",
]

CHUNK_RE = re.compile(r"/assets/[A-Za-z0-9_.\-]+\.js")
KEYWORDS = [
    "fetch(",
    "XMLHttpRequest",
    "WebSocket",
    "better-admin",
    "bookings.better",
    "islington",
    "highbury",
    "clissold",
    "supabase",
    "firebaseio",
    "firestore",
    ".workers.dev",
    "vercel.app",
    "railway.app",
    "onrender.com",
    "fly.dev",
    "herokuapp",
    "/functions/",
    "graphql",
    "axios",
    "baseURL",
    "VITE_",
    "import.meta.env",
]


def dump_bundle(url: str, seen_chunks: set) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
    except Exception as e:
        print(f"\n=== {url} -> ERROR {e} ===")
        return ""

    print(f"\n=== {url} ===")
    print("status:", r.status_code, "len:", len(r.content))
    if not r.ok:
        return ""

    text = r.text

    for kw in KEYWORDS:
        idx = 0
        count = 0
        while True:
            pos = text.find(kw, idx)
            if pos == -1 or count >= 5:
                break
            start = max(0, pos - 80)
            end = min(len(text), pos + 120)
            print(f"\n[{kw}] ...{text[start:end]}...")
            idx = pos + len(kw)
            count += 1

    for chunk in CHUNK_RE.findall(text):
        seen_chunks.add(chunk)

    return text


def main() -> int:
    seen_chunks: set = set(SEED_BUNDLES)
    processed: set = set()

    queue = list(SEED_BUNDLES)
    while queue:
        path = queue.pop(0)
        if path in processed:
            continue
        processed.add(path)
        dump_bundle(BASE + path, seen_chunks)
        for c in seen_chunks:
            if c not in processed and c not in queue:
                queue.append(c)

    print(f"\n--- discovered {len(seen_chunks)} total chunk path(s) ---")
    for c in sorted(seen_chunks):
        print(c)

    return 0


if __name__ == "__main__":
    sys.exit(main())
