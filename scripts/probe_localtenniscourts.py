#!/usr/bin/env python3
"""Probe localtenniscourts.com to discover its real data shape (JSON API vs rendered HTML).

tennis_app/wednesday_watch.py parses this page with heuristics that have never been
checked against a real response -- this sandbox's proxy blocks the domain, the same way it
blocks better-admin.org.uk (see CLAUDE.md gotchas). Run this script somewhere with real
network egress (e.g. a throwaway GitHub Actions push-triggered workflow, per the existing
repo convention for probing better-admin.org.uk in scripts/probe_venue.py) and read the
output to confirm whether the page embeds JSON state or needs pure HTML scraping.

Usage:
    python scripts/probe_localtenniscourts.py
    python scripts/probe_localtenniscourts.py --url "https://localtenniscourts.com/?q=..."
"""

import argparse
import sys

import requests

from tennis_app.wednesday_watch import DEFAULT_URL, EMBEDDED_JSON_PATTERNS, HEADERS


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default=DEFAULT_URL, help="Page URL to probe")
    p.add_argument(
        "--dump-chars",
        type=int,
        default=3000,
        help="How many HTML chars to print if no JSON is found",
    )
    args = p.parse_args(argv)

    r = requests.get(args.url, headers=HEADERS, timeout=15)
    print(
        f"status={r.status_code} content-type={r.headers.get('content-type')} bytes={len(r.content)}"
    )

    found_any = False
    for i, pattern in enumerate(EMBEDDED_JSON_PATTERNS):
        m = pattern.search(r.text)
        if m:
            found_any = True
            print(f"\n--- embedded JSON pattern #{i} matched ({pattern.pattern[:40]}...) ---")
            print(m.group(1)[:2000])

    if not found_any:
        print("\nNo known embedded-JSON pattern matched.")
        print(f"Dumping first {args.dump_chars} chars of HTML for manual inspection:\n")
        print(r.text[: args.dump_chars])
        print(
            "\nAlso check your browser's Network tab (XHR/Fetch filter) while loading the "
            "page -- if slots load via an API call after page load, this static fetch won't "
            "see it and the real endpoint needs to be called directly instead."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
