#!/usr/bin/env python3
"""One-shot probe: does localtenniscourts.com expose a JSON API backing its
court-availability page, or is HTML scraping the only option?

Throwaway script - run via a GitHub Actions job (real egress), read the log,
then delete both this file and its workflow.
"""

import re
import sys

import requests

PAGE_URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

INTERESTING = re.compile(
    r"(/api/[^\"'\s]*|\.json[^\"'\s]*|fetch\(\s*[\"'][^\"']+|axios\.\w+\(\s*[\"'][^\"']+"
    r"|XMLHttpRequest|__NEXT_DATA__|__NUXT__|window\.__\w*STATE\w*__|wp-json|graphql)",
    re.IGNORECASE,
)


def fetch(url: str, **kw) -> requests.Response | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, **kw)
        print(f"GET {url} -> {r.status_code} ({len(r.content)} bytes, {r.headers.get('content-type')})")
        return r
    except Exception as e:
        print(f"GET {url} -> ERROR {e}")
        return None


def main() -> int:
    r = fetch(PAGE_URL)
    if r is None or not r.ok:
        print("Could not fetch main page; aborting further analysis.")
        return 1

    html = r.text
    print(f"\n--- first 2000 chars of body ---\n{html[:2000]}\n--- end excerpt ---\n")

    matches = sorted(set(m.group(0) for m in INTERESTING.finditer(html)))
    print(f"\n--- {len(matches)} interesting pattern(s) in main page HTML ---")
    for m in matches:
        print(repr(m))

    # Collect script src URLs (both absolute and root-relative)
    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
    from urllib.parse import urljoin

    script_urls = [urljoin(PAGE_URL, s) for s in script_srcs]
    print(f"\n--- {len(script_urls)} script tag(s) found ---")
    for su in script_urls:
        print(su)

    # Fetch same-origin scripts and scan them too (skip obvious third-party CDNs to save requests)
    for su in script_urls:
        if "localtenniscourts.com" not in su:
            continue
        rs = fetch(su)
        if rs is None or not rs.ok:
            continue
        js = rs.text
        jmatches = sorted(set(m.group(0) for m in INTERESTING.finditer(js)))
        if jmatches:
            print(f"\n--- interesting pattern(s) in {su} ---")
            for m in jmatches[:40]:
                print(repr(m))

    # A few common API/data guesses worth a direct shot in the dark
    guesses = [
        "https://localtenniscourts.com/wp-json/",
        "https://localtenniscourts.com/api/courts",
        "https://localtenniscourts.com/api/availability",
        "https://localtenniscourts.com/robots.txt",
    ]
    print("\n--- direct guesses ---")
    for g in guesses:
        fetch(g)

    return 0


if __name__ == "__main__":
    sys.exit(main())
