"""Pipeline: the main orchestration that takes raw records and runs the business logic."""

import logging
from typing import Any

import polars as pl

from tennis_app.cache import load_prev_rows, save_rows
from tennis_app.config import WATCH_HOUR_FROM, WATCH_WEEKDAY
from tennis_app.notify import send_email
from tennis_app.transform import filter_watch_window, newly_available_slots, tabularise


def run(
    raw_records: list[dict[str, Any]],
    cache_path: str,
    *,
    notify: bool = True,
) -> pl.DataFrame:
    """
    Execute the full pipeline:
      1. Transform raw API records into a clean table
      2. Load the previously-cached table
      3. Filter both to the watch window (WATCH_WEEKDAY at/after WATCH_HOUR_FROM)
         and find slots that flipped from booked to free
      4. Optionally send an email for any such slots
      5. Save the current table to cache

    Args:
        raw_records: List of activity dicts (from the API or from fixtures).
        cache_path: Path to the JSON cache file.
        notify: If True (default), send email on changes. Set False for testing.

    Returns:
        The current transformed DataFrame.
    """
    logging.info("Tabularising %d raw records…", len(raw_records))
    curr_df = tabularise(raw_records)

    logging.info("Loading previous rows from cache…")
    prev_df = load_prev_rows(cache_path)

    watched_curr = filter_watch_window(curr_df, WATCH_WEEKDAY, WATCH_HOUR_FROM)
    watched_prev = filter_watch_window(prev_df, WATCH_WEEKDAY, WATCH_HOUR_FROM)

    logging.info("Checking for newly-available watched slots…")
    newly_free = newly_available_slots(watched_curr, watched_prev)

    if not newly_free.is_empty():
        if notify:
            logging.info("Sending email for %d newly-available slot(s)…", len(newly_free))
            send_email("Tennis slots just opened up", newly_free)
        else:
            logging.info(
                "%d newly-available slot(s) detected but notifications disabled.", len(newly_free)
            )
    else:
        logging.info("No newly-available watched slots.")

    logging.info("Saving current rows back to cache…")
    save_rows(cache_path, curr_df)
    return curr_df
