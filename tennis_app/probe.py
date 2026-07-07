"""One-off discovery probe: confirm which Better Admin venue/activity slugs are real.

This environment (and local dev) cannot reach the booking API, so we verify the
Highbury Fields activity slug from CI, where the network is open. Run it via the
"Probe venue slugs" GitHub Actions workflow (workflow_dispatch) and read the logs.

    python -m tennis_app.probe

For each candidate (venue, activity) pair it fetches the next few days and reports
how many slots came back, plus a sample — so a real slug is obvious from the log.
"""

import logging
from datetime import datetime, timedelta

from tennis_app.fetch import fetch_activities

# Hypotheses for the two outdoor sites in the brief. The Islington outdoor pair
# is already known-good and acts as a positive control. The rest are candidates
# for Highbury Fields, whose booking page lives at
# bookings.better.org.uk/location/islington-tennis-centre/highbury-fields-activities
CANDIDATES: list[tuple[str, str]] = [
    ("islington-tennis-centre", "tennis-court-outdoor"),  # control (known-good)
    ("islington-tennis-centre", "highbury-fields-tennis"),
    ("islington-tennis-centre", "highbury-fields-activities"),
    ("islington-tennis-centre", "highbury-fields-outdoor-tennis"),
    ("islington-tennis-centre", "highbury-fields"),
    ("highbury-fields", "tennis-court-outdoor"),
    ("highbury-fields", "tennis-court"),
]


def probe(candidates: list[tuple[str, str]] | None = None, days_ahead: int = 3) -> None:
    candidates = candidates or CANDIDATES
    today = datetime.now().date()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_ahead)]

    logging.info("=== Probing %d candidate slug(s) over %s ===", len(candidates), dates)
    hits: list[tuple[str, str, int]] = []

    for venue, court in candidates:
        total = 0
        sample = ""
        for d in dates:
            try:
                records = fetch_activities(venue, court, d)
            except Exception as e:  # noqa: BLE001 - report and keep probing
                logging.info("  %-30s/%-32s %s -> ERROR: %s", venue, court, d, e)
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
