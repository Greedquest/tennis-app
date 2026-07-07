"""One-off discovery probe: confirm which Better Admin venue/activity slugs are real.

This environment (and local dev) cannot reach the booking API, so we verify the
Highbury Fields activity slug from CI, where the network is open. Run it via the
"Probe venue slugs" GitHub Actions workflow (workflow_dispatch) and read the logs.

    python -m tennis_app.probe

For each candidate (venue, activity) pair it fetches the next few days and reports
how many slots came back, plus a sample — so a real slug is obvious from the log.
"""

import logging
import time
from datetime import datetime, timedelta

from tennis_app.fetch import fetch_activities

# Candidates for the two outdoor sites in the brief.
#
# A prior probe established the error semantics of the times endpoint:
#   * 404 -> the venue/activity slug does not exist
#   * 422 -> the venue/activity pair IS recognised (same response the known-good
#            "tennis-court-outdoor" slug gives); a burst of requests gets throttled
#   * 200 -> served (n_records may be 0 if nothing is on that date)
# So "highbury-fields-activities" under islington-tennis-centre (422, matching the
# booking URL .../location/islington-tennis-centre/highbury-fields-activities) is
# the leading Highbury candidate, and "islington-parks" is a valid sibling venue.
CANDIDATES: list[tuple[str, str]] = [
    ("islington-tennis-centre", "tennis-court-outdoor"),  # control (known-good)
    ("islington-tennis-centre", "highbury-fields-activities"),  # leading Highbury slug
    ("islington-parks", "tennis-court-outdoor"),
    ("islington-parks", "highbury-fields-activities"),
]

# Seconds to wait between requests. The API 422s under bursty load, so pace it
# to get a clean read (the real poller fires only a handful of requests / poll).
PROBE_DELAY_S = 4.0


def probe(candidates: list[tuple[str, str]] | None = None, days_ahead: int = 2) -> None:
    candidates = candidates or CANDIDATES
    today = datetime.now().date()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_ahead)]

    logging.info("=== Probing %d candidate slug(s) over %s ===", len(candidates), dates)
    hits: list[tuple[str, str, int]] = []

    for venue, court in candidates:
        total = 0
        sample = ""
        for d in dates:
            time.sleep(PROBE_DELAY_S)
            try:
                records = fetch_activities(venue, court, d)
            except Exception as e:  # noqa: BLE001 - report and keep probing
                logging.info("  %-24s/%-32s %s -> ERROR: %s", venue, court, d, e)
                continue
            total += len(records)
            if records and not sample:
                r0 = records[0]
                starts = (r0.get("starts_at") or {}).get("format_24_hour")
                sample = f"e.g. {r0.get('date')} {starts} spaces={r0.get('spaces')}"

        marker = "  <-- REAL" if total else ""
        logging.info("  %-24s / %-32s -> %3d slot(s) %s%s", venue, court, total, sample, marker)
        if total:
            hits.append((venue, court, total))

    logging.info("=== Confirmed slugs ===")
    if hits:
        for venue, court, total in hits:
            logging.info('  {"venue": "%s", "court": "%s"}  (%d slots)', venue, court, total)
    else:
        logging.warning("  No candidate returned data — none of the guessed slugs are valid.")


if __name__ == "__main__":
    probe()
