#!/usr/bin/env python3
"""One-shot probe: does localtenniscourts.com expose a JSON API?

Throwaway diagnostic for wiring up a new local availability monitor
(see the brief for a 5-minute Wednesday-afternoon watcher). Not part of
the app - run once from a GitHub Actions job (this sandbox's egress
proxy blocks the domain), read the logs, then delete this file and its
workflow.

Prints:
  - status/headers for the search page itself
  - any embedded JSON blobs (__NEXT_DATA__, __NUXT__, apollo state, etc.)
  - script src URLs, so a JS bundle can be grepped for API base paths
  - a handful of guessed API endpoints, for a quick first pass
"""

import json
import re
import sys

import requests

BASE = "https://localtenniscourts.com"
PAGE_URL = f"{BASE}/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

EMBEDDED_JSON_PATTERNS = [
    ("__NEXT_DATA__", re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)),
    ("__NUXT__", re.compile(r"window\.__NUXT__\s*=\s*(\{.*?\});?\s*</script>", re.S)),
    ("__APOLLO_STATE__", re.compile(r"__APOLLO_STATE__\s*=\s*(\{.*?\});?\s*</script>", re.S)),
    ("generic window.__*__", re.compile(r"window\.(__[A-Z_]+__)\s*=\s*(\{.*?\});", re.S)),
]

GUESS_ENDPOINTS = [
    "/api/venues",
    "/api/courts",
    "/api/search",
    "/api/availability",
    "/api/venues/highbury-fields",
    "/robots.txt",
    "/sitemap.xml",
]


def section(title: str) -> None:
    print(f"\n{'=' * 10} {title} {'=' * 10}")


def fetch_page() -> str:
    section(f"GET {PAGE_URL}")
    r = requests.get(PAGE_URL, headers=HEADERS, timeout=20)
    print("status:", r.status_code)
    print("headers:", json.dumps(dict(r.headers), indent=2))
    print("body length:", len(r.text))
    return r.text


def find_embedded_json(html: str) -> None:
    section("Embedded JSON blobs")
    found_any = False
    for name, pattern in EMBEDDED_JSON_PATTERNS:
        for m in pattern.finditer(html):
            found_any = True
            blob = m.group(1) if m.lastindex == 1 else m.group(2)
            print(f"--- {name} ({len(blob)} chars) ---")
            try:
                parsed = json.loads(blob)
                print(json.dumps(parsed, indent=2)[:8000])
            except Exception as e:
                print(f"(unparsed, {e}); raw prefix:")
                print(blob[:2000])
    if not found_any:
        print("none found")


def find_script_srcs(html: str) -> None:
    section("Script src attributes")
    srcs = re.findall(r'<script[^>]+src="([^"]+)"', html)
    for s in sorted(set(srcs)):
        print(s)


def dump_raw_html(html: str) -> None:
    # This app streams a giant single-line seroval ($R[...]=...) payload,
    # not a <script id="..."> JSON blob. Chunk it so the GH Actions log
    # renderer doesn't choke on one 90KB line, and print all of it.
    section(f"Raw HTML, full body ({len(html)} chars), chunked")
    chunk = 2000
    for i in range(0, len(html), chunk):
        print(html[i : i + chunk])


def grep_context(html: str, needles: list[str], radius: int = 400) -> None:
    section("Keyword search in HTML")
    for needle in needles:
        idxs = [m.start() for m in re.finditer(re.escape(needle), html)]
        print(f"\n--- {needle!r}: {len(idxs)} occurrence(s) ---")
        for idx in idxs[:5]:
            lo, hi = max(0, idx - radius), min(len(html), idx + radius)
            print(f"[@{idx}] …{html[lo:hi]}…")


def fetch_and_grep_bundle(html: str) -> None:
    section("JS bundle inspection")
    srcs = re.findall(r'href="(/assets/[^"]+\.js)"', html) + re.findall(
        r"import\('(/assets/[^']+\.js)'\)", html
    )
    for src in sorted(set(srcs)):
        url = BASE + src
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            print(f"\n--- {url} ({len(r.text)} chars) ---")
            for needle in (
                "/api/",
                "fetch(",
                "serverFn",
                "trpc",
                "better-admin",
                "clubspark",
                "courtside",
                "playfinder",
                "bookteq",
                "createServerFn",
            ):
                idxs = [m.start() for m in re.finditer(re.escape(needle), r.text)]
                if idxs:
                    print(f"  found {needle!r} x{len(idxs)}, first context:")
                    idx = idxs[0]
                    print("   ", r.text[max(0, idx - 150) : idx + 150])
        except Exception as e:
            print(f" ERR  {url}  {e}")


def try_guessed_endpoints() -> None:
    section("Guessed endpoints")
    for path in GUESS_ENDPOINTS:
        url = BASE + path
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            ctype = r.headers.get("content-type", "")
            print(f"{r.status_code:4} {ctype:30} {url}  ({len(r.content)} bytes)")
            if "json" in ctype:
                print(r.text[:2000])
        except Exception as e:
            print(f" ERR  {url}  {e}")


def main() -> int:
    html = fetch_page()
    find_embedded_json(html)
    find_script_srcs(html)
    grep_context(
        html,
        [
            "spaces",
            "starts_at",
            "start_time",
            "available",
            "timeslot",
            "slots",
            "id:1,",
            "id:5,",
            "highbury",
            "islington-tennis-centre",
        ],
    )
    fetch_and_grep_bundle(html)
    dump_raw_html(html)
    try_guessed_endpoints()
    return 0


if __name__ == "__main__":
    sys.exit(main())
