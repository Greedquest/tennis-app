"""Fetch activity data from the Better Admin API."""

import logging
from datetime import datetime, timedelta
from typing import Any

import requests

from tennis_app.config import VENUES


def fetch_activities(venue: str, court: str, date: str) -> list[dict[str, Any]]:
    """
    Fetch activity data from the Better Admin API for a specific venue, court, and date.

    Args:
        venue: Venue identifier (e.g., "islington-tennis-centre")
        court: Court/activity identifier (e.g., "tennis-court-indoor")
        date: Date in YYYY-MM-DD format

    Returns:
        List of activity records from the API "data" array
    """
    url = f"https://better-admin.org.uk/api/activities/venue/{venue}/activity/{court}/times"
    headers = {
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
    params = {"date": date}

    r = requests.get(url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    response_data = r.json()

    return response_data.get("data", [])


def fetch_all_activities(
    venues: list[dict[str, str]] | None = None,
    days_ahead: int = 5,
) -> list[dict[str, Any]]:
    """
    Fetch activities for all venue/court combinations for the next N days.

    Args:
        venues: List of venue/court dicts. Defaults to VENUES from config.
        days_ahead: Number of days ahead to fetch (default 5).

    Returns:
        List of raw activity dicts, each enriched with "venue" and "court" keys.
    """
    if venues is None:
        venues = VENUES

    today = datetime.now().date()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_ahead)]

    all_records: list[dict[str, Any]] = []
    fetch_errors: list[str] = []

    for venue_court in venues:
        venue = venue_court["venue"]
        court = venue_court["court"]

        for date in dates:
            try:
                logging.info("Fetching %s/%s for %s...", venue, court, date)
                activities = fetch_activities(venue, court, date)

                for activity in activities:
                    if not isinstance(activity, dict):
                        continue
                    activity["venue"] = venue
                    activity["court"] = court
                    all_records.append(activity)

            except Exception as e:
                logging.warning("Failed to fetch %s/%s for %s: %s", venue, court, date, e)
                fetch_errors.append(f"{venue}/{court} for {date}: {e}")
                continue

    total_attempts = len(venues) * len(dates)

    if fetch_errors and not all_records:
        raise RuntimeError(
            f"All {len(fetch_errors)} fetch attempt(s) failed. "
            f"First error: {fetch_errors[0]}"
        )

    if fetch_errors:
        logging.warning(
            "%d of %d fetch attempts failed; returning partial results.",
            len(fetch_errors),
            total_attempts,
        )

    return all_records
