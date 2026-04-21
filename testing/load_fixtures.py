"""Helpers for loading fixture data in tests or local development.

Usage::

    from testing.load_fixtures import load_enriched_records, load_api_sample
    records = load_enriched_records()          # list[dict] ready for pipeline.run()
    api_resp = load_api_sample()               # raw {"data": [...]} API response
"""

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_enriched_records() -> list[dict[str, Any]]:
    """Return the pre-enriched activity records (same shape as fetch_all_activities output)."""
    path = FIXTURES_DIR / "enriched_records.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_api_sample() -> dict[str, Any]:
    """Return a single raw API response (with top-level "data" array)."""
    path = FIXTURES_DIR / "actual_api_sample.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)
