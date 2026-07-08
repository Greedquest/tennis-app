#!/usr/bin/env python3
"""Probe the Better Admin API to discover valid venue / activity (court) slugs.

The booking data this project polls comes from:

    https://better-admin.org.uk/api/activities/venue/{venue}/activity/{court}/times?date=YYYY-MM-DD

Adding a new venue to ``tennis_app/config.py`` means knowing its exact
``venue`` and ``court`` slugs, which aren't published anywhere obvious. This
utility takes one or more ``venue:court`` candidates and reports, for each, the
HTTP status and number of slot records returned across a range of dates — so
you can confirm a slug is live before wiring it in.

Why a standalone script and not an app module:
  - The booking API is often unreachable from sandboxes / CI proxies (they
    return 403). Run this where there's real network egress, e.g. a GitHub
    Actions job, and read the output.
  - The API rate-limits bursts: firing many requests back to back can return
    spurious 422s even for a known-good slug. Keep a known-good pair in the
    list as a control and raise ``--delay`` if healthy pairs start failing.

Reading the output:
  - 200 with records  -> live, valid slug.
  - 200 with 0 records -> slug is structurally valid but had nothing on that
    date (could still be right; try more dates).
  - 404               -> unknown slug.
  - 422 across the board, including the control -> you're being rate-limited.

Examples:
    python scripts/probe_venue.py islington-parks:tennis-court-outdoor
    python scripts/probe_venue.py \
        islington-tennis-centre:tennis-court-outdoor \
        islington-parks:tennis-court-outdoor \
        islington-parks:highbury-fields-activities \
        --days 7 --delay 1.5
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta

import requests

API = "https://better-admin.org.uk/api/activities/venue/{venue}/activity/{court}/times"

HEADERS = {
    "Origin": "https://bookings.better.org.uk",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://bookings.better.org.uk/",
}

# Sensible default: a known-good control plus the Highbury Fields slug.
#
# "islington-tennis-centre:highbury-tennis" is not yet confirmed by a live probe
# from this repo (Better Admin returned 422 for every candidate incl. the control
# on the last attempt - looks like rate-limiting, not a bad slug; retry with a
# longer --delay). It comes from localtenniscourts.com, a third-party aggregator
# that server-renders scraped Better Admin data inline in its HTML (view source,
# no separate API call needed) - its own "book now" links for Highbury Fields
# point at https://bookings.better.org.uk/location/islington-tennis-centre/highbury-tennis/...
DEFAULT_CANDIDATES = [
    "islington-tennis-centre:tennis-court-outdoor",  # known-good control
    "islington-tennis-centre:highbury-tennis",
]


def parse_pair(value: str) -> tuple[str, str]:
    """Parse a ``venue:court`` argument into a (venue, court) tuple."""
    venue, sep, court = value.partition(":")
    if not sep or not venue or not court:
        raise argparse.ArgumentTypeError(f"expected venue:court, got {value!r}")
    return venue, court


def probe(candidates: list[tuple[str, str]], days: int, delay: float) -> list[dict]:
    """Probe each (venue, court) across ``days`` dates, pacing by ``delay`` seconds."""
    dates = [(datetime.now().date() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

    results: list[dict] = []
    for venue, court in candidates:
        url = API.format(venue=venue, court=court)
        for date in dates:
            # Every record has the same shape (success or error) so the JSON
            # summary stays trivially consumable.
            record: dict[str, object] = {
                "venue": venue,
                "court": court,
                "date": date,
                "status": None,
                "n_records": None,
                "sample": None,
                "error": None,
            }
            try:
                r = requests.get(url, headers=HEADERS, params={"date": date}, timeout=15)
                n_records: int | str | None = None
                sample = None
                if r.ok:
                    try:
                        data = r.json().get("data", [])
                        n_records = len(data)
                        sample = data[0] if data else None
                    except Exception:
                        n_records = "unparseable"
                record["status"] = r.status_code
                record["n_records"] = n_records
                record["sample"] = sample
                print(f"{r.status_code:4} n={str(n_records):>6}  {date}  {venue}:{court}")
            except Exception as e:  # noqa: BLE001 - diagnostic tool, report and continue
                record["error"] = str(e)
                print(f" ERR  {date}  {venue}:{court}  {e}")
            results.append(record)
            time.sleep(delay)
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Probe Better Admin API venue/court slugs.")
    p.add_argument(
        "candidates",
        nargs="*",
        type=parse_pair,
        help="venue:court pairs to probe (defaults to a built-in control set)",
    )
    p.add_argument("--days", type=int, default=7, help="dates ahead to check (default 7)")
    p.add_argument(
        "--delay", type=float, default=1.5, help="seconds between requests (default 1.5)"
    )
    args = p.parse_args(argv)

    candidates = args.candidates or [parse_pair(s) for s in DEFAULT_CANDIDATES]
    results = probe(candidates, days=args.days, delay=args.delay)

    print("\n--- SUMMARY (JSON) ---")
    print(json.dumps(results, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
