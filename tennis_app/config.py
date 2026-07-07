"""Configuration: venue definitions, environment variables, logging."""

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

# Venue/Court combinations to poll
VENUES = [
    {"venue": "islington-tennis-centre", "court": "tennis-court-indoor"},
    {"venue": "islington-tennis-centre", "court": "tennis-court-outdoor"},
    # NOTE: slug unverified — better-admin.org.uk was unreachable from the
    # sandbox that added this entry (blocked by egress policy). If the
    # poller logs "Failed to fetch highbury-fields/tennis-court-outdoor",
    # check bookings.better.org.uk/location/highbury-fields for the real
    # venue/court slugs and correct this.
    {"venue": "highbury-fields", "court": "tennis-court-outdoor"},
]

# "Wednesday evening watch": alert only when a slot starting at/after this
# 24-hour time on a Wednesday flips from fully booked to available.
WEDNESDAY_EVENING_MIN_TIME = os.getenv("WEDNESDAY_EVENING_MIN_TIME", "19:00")
