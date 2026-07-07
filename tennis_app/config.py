"""Configuration: venue definitions, monitoring window, env vars, logging."""

import logging
import os

# ---- config from env ----
CACHE_STATE_PATH = os.getenv("CACHE_STATE_PATH", "cache/state.json")

EMAIL_FROM = os.getenv("EMAIL_FROM", "")  # authorized Gmail address
EMAIL_TO = os.getenv("EMAIL_TO", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")  # Gmail app password

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)

# ---- what to monitor ----
# Venue/Court combinations to poll.  Each "court" is the Better Admin
# *activity* slug used by the times endpoint:
#   https://better-admin.org.uk/api/activities/venue/<venue>/activity/<court>/times
#
# Per the brief we watch the two outdoor sites reachable from
# localtenniscourts.com?q=highbury-fields,islington-tennis-centre-outdoor:
#   * Highbury Fields  (11 floodlit outdoor courts, managed by Islington TC)
#   * Islington Tennis Centre outdoor
#
# Slugs verified in CI (tennis_app.probe): both live under the
# islington-tennis-centre venue.  "highbury-fields-activities" matches the
# booking URL bookings.better.org.uk/location/islington-tennis-centre/
# highbury-fields-activities and returns the same recognised response as the
# known-good "tennis-court-outdoor" slug (candidates like "highbury-fields" or
# venue "highbury-fields" 404).
VENUES = [
    {"venue": "islington-tennis-centre", "court": "highbury-fields-activities"},
    {"venue": "islington-tennis-centre", "court": "tennis-court-outdoor"},
]

# ---- when to alert ----
# The brief: "Alert the moment a slot after 19:00 on Wednesday opens up."
TZ_NAME = os.getenv("TZ_NAME", "Europe/London")
TARGET_WEEKDAY = int(os.getenv("TARGET_WEEKDAY", "2"))  # Mon=0 … Wed=2
TARGET_MIN_HOUR = int(os.getenv("TARGET_MIN_HOUR", "19"))  # start times >= 19:00

# Poll window (local time, inclusive-exclusive): midday to 22:00.  Runs
# outside this window (e.g. a stray manual dispatch) log quietly and exit.
POLL_START_HOUR = int(os.getenv("POLL_START_HOUR", "12"))
POLL_END_HOUR = int(os.getenv("POLL_END_HOUR", "22"))
