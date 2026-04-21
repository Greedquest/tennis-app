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
]
