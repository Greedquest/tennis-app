#!/usr/bin/env python3
"""Throwaway probe: inspect localtenniscourts.com for an underlying JSON API.

Not part of the app. Run once from an environment with real internet egress
(this sandbox's proxy 403s most booking-adjacent domains), read the output,
then delete this file and its probe workflow.
"""

import re
import sys

import requests

BASE = "https://localtenniscourts.com/"
QUERY = "?q=highbury-fields,islington-tennis-centre-outdoor"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SCRIPT_SRC_RE = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
MODULEPRELOAD_RE = re.compile(r'<link[^>]+rel=["\']modulepreload["\'][^>]+href=["\']([^"\']+)["\']', re.IGNORECASE)
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
API_LIKE_RE = re.compile(
    r'["\']((?:https?:)?//[^"\']*|/[a-zA-Z0-9_\-./]*(?:api|json|supabase|firebase|worker|function)[^"\']*)["\']',
    re.IGNORECASE,
)


def get(url: str) -> requests.Response:
    print(f"\n=== GET {url} ===")
    r = requests.get(url, headers=HEADERS, timeout=20)
    print(f"status={r.status_code} len={len(r.content)} content-type={r.headers.get('content-type')}")
    return r


def main() -> int:
    r = get(BASE + QUERY)
    r.raise_for_status()
    html = r.text

    print("\n--- first 2000 chars of HTML ---")
    print(html[:2000])

    next_data = NEXT_DATA_RE.search(html)
    if next_data:
        print("\n--- __NEXT_DATA__ found (first 4000 chars) ---")
        print(next_data.group(1)[:4000])
    else:
        print("\n--- no __NEXT_DATA__ block found ---")

    scripts = SCRIPT_SRC_RE.findall(html)
    modulepreloads = MODULEPRELOAD_RE.findall(html)
    print(f"\n--- {len(scripts)} <script src> tags ---")
    for s in scripts:
        print(s)
    print(f"\n--- {len(modulepreloads)} <link rel=modulepreload> tags ---")
    for m in modulepreloads:
        print(m)

    all_js = list(scripts) + list(modulepreloads)

    # Fetch same-origin JS bundles and grep them for API endpoint patterns.
    for s in all_js:
        if s.startswith("http") and "localtenniscourts.com" not in s:
            continue
        url = s if s.startswith("http") else (BASE.rstrip("/") + "/" + s.lstrip("/"))
        try:
            jr = get(url)
        except Exception as e:
            print(f"  failed to fetch {url}: {e}")
            continue
        if not jr.ok:
            continue
        body = jr.text
        hits = sorted(set(API_LIKE_RE.findall(body)))
        print(f"  {len(hits)} api/url-like strings in {url} (showing up to 80):")
        for h in hits[:80]:
            print(f"    {h}")

    # Broader pass: fetch/axios call sites and court/venue-ish path fragments,
    # in case the base URL is built from env vars rather than a literal string.
    CALL_SITE_RE = re.compile(r'.{0,60}(?:fetch\(|axios\.(?:get|post)\()')
    PATH_FRAGMENT_RE = re.compile(
        r'["\']([^"\']{0,80}(?:court|venue|booking|slot|highbury|islington|clissold|regent|finsbury|hackney|rosemary)[^"\']{0,80})["\']',
        re.IGNORECASE,
    )
    for s in all_js:
        if s.startswith("http") and "localtenniscourts.com" not in s:
            continue
        url = s if s.startswith("http") else (BASE.rstrip("/") + "/" + s.lstrip("/"))
        try:
            body = requests.get(url, headers=HEADERS, timeout=20).text
        except Exception:
            continue
        call_sites = CALL_SITE_RE.findall(body)
        print(f"\n--- {len(call_sites)} fetch/axios call sites in {url} ---")
        for c in call_sites[:30]:
            print(f"    ...{c}")
        frags = sorted(set(PATH_FRAGMENT_RE.findall(body)))
        print(f"--- {len(frags)} court/venue-ish string fragments in {url} ---")
        for f in frags[:60]:
            print(f"    {f}")

    # A few common guesses, just in case.
    for guess in ["api/availability", "api/courts", "api/slots", "api/venues", "robots.txt", "sitemap.xml"]:
        try:
            gr = get(BASE + guess)
            if gr.ok:
                print(f"  --- body preview for {guess} ---")
                print(gr.text[:1000])
        except Exception as e:
            print(f"  failed to fetch guess {guess}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
