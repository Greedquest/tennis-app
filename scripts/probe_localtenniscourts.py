#!/usr/bin/env python3
"""Probe localtenniscourts.com to discover its underlying data source.

This sandbox's egress proxy denies localtenniscourts.com outright (403 at
the CONNECT step), so this can only be run somewhere with real internet
access, e.g. a throwaway GitHub Actions job on a runner (see the
"Gotchas" section of CLAUDE.md for the established pattern: push a
probe workflow, read the job logs, then delete the workflow).

It drives a headless browser to the query page, records every network
request the page makes, and prints anything that looks like a JSON/XHR
data call plus a snippet of its response body -- so we can tell whether
the site is backed by a discoverable API or whether HTML scraping is the
only option.
"""

import json
import re
import sys

import requests
from playwright.sync_api import sync_playwright

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"


def main() -> int:
    calls: list[dict] = []
    requests_seen: list[dict] = []
    failures: list[dict] = []
    script_srcs: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_request(request):
            if request.resource_type in ("image", "stylesheet", "font", "media"):
                return
            requests_seen.append(
                {"method": request.method, "url": request.url, "resource_type": request.resource_type}
            )
            if request.resource_type == "script":
                script_srcs.append(request.url)

        def on_request_failed(request):
            failures.append(
                {
                    "url": request.url,
                    "method": request.method,
                    "resource_type": request.resource_type,
                    "failure": request.failure,
                }
            )

        def on_response(response):
            req = response.request
            if req.resource_type in ("image", "stylesheet", "font", "media"):
                return
            if "google-analytics" in response.url or "cdn-cgi/rum" in response.url:
                return
            content_type = response.headers.get("content-type", "")
            entry = {
                "method": req.method,
                "url": response.url,
                "status": response.status,
                "content_type": content_type,
                "resource_type": req.resource_type,
            }
            if "json" in content_type or req.resource_type in ("xhr", "fetch"):
                try:
                    body = response.text()
                    entry["body_snippet"] = body[:2000]
                except Exception as e:  # noqa: BLE001 - diagnostic tool
                    entry["body_error"] = str(e)
            calls.append(entry)

        page.on("request", on_request)
        page.on("requestfailed", on_request_failed)
        page.on("response", on_response)

        print(f"Navigating to {URL} ...", file=sys.stderr)
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(5000)  # settle any late XHRs / retries

        html = page.content()
        body_text = page.inner_text("body")

        browser.close()

    print("\n--- ALL NON-STATIC REQUESTS ISSUED ---")
    print(json.dumps(requests_seen, indent=2, default=str))

    print("\n--- FAILED REQUESTS ---")
    print(json.dumps(failures, indent=2, default=str))

    print("\n--- NETWORK CALLS (JSON) ---")
    print(json.dumps(calls, indent=2, default=str))

    print(f"\n--- RENDERED HTML LENGTH: {len(html)} ---")

    print("\n--- SCRIPT TAGS (src or inline snippets) ---")
    for m in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.S):
        tag = m.group(0)
        if "src=" in tag[:200]:
            src_match = re.search(r'src="([^"]+)"', tag)
            if src_match:
                print("SRC:", src_match.group(1))
        else:
            inline = m.group(1).strip()
            if inline and any(
                k in inline for k in ("__NEXT_DATA__", "__INITIAL_STATE__", "wednesday", "slot", "court", "api")
            ):
                print("INLINE SNIPPET:", inline[:1500])

    print("\n--- BODY INNER TEXT (first 4000 chars) ---")
    print(body_text[:4000])

    print("\n--- HTML SNIPPETS MENTIONING 'wednesday' or 'court' (case-insensitive) ---")
    for m in re.finditer(r".{200}(?:wednesday|court|available|book).{200}", html, re.I | re.S):
        print(m.group(0))
        print("---")

    print("\n--- SEARCHING JS BUNDLES FOR API URLS / FETCH CALLS ---")
    for src in dict.fromkeys(script_srcs):  # de-dupe, keep order
        if not src.startswith("https://localtenniscourts.com/"):
            continue  # skip third-party scripts (analytics, widgets)
        try:
            r = requests.get(src, timeout=15)
            body = r.text
        except Exception as e:  # noqa: BLE001 - diagnostic tool
            print(f"{src}: FETCH FAILED: {e}")
            continue
        print(f"\n{src} ({len(body)} bytes)")
        # Look for absolute URLs and common API-ish substrings
        urls = set(re.findall(r"https?://[a-zA-Z0-9.\-]+(?:/[^\"'\s)]*)?", body))
        api_like = {
            u
            for u in urls
            if "localtenniscourts.com" not in u
            and "w3.org" not in u
            and "googletagmanager" not in u
        }
        if api_like:
            print("External URLs referenced:")
            for u in sorted(api_like):
                print(" ", u)
        for kw in ("/api/", "supabase", "workers.dev", "fetch(", "axios", "VITE_API"):
            idxs = [m.start() for m in re.finditer(re.escape(kw), body)]
            for idx in idxs[:5]:
                print(f"  ...{kw!r} @ {idx}: {body[max(0, idx - 80):idx + 120]!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
