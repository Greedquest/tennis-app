"""Pipeline: the main orchestration that takes raw records and runs the business logic."""

import logging
from typing import Any

import polars as pl

from tennis_app.cache import load_prev_rows, save_rows
from tennis_app.notify import send_email
from tennis_app.transform import key_of, tabularise, wednesday_evening_openings


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
      3. Find Wednesday >=19:00 slots that flipped from booked to free
      4. Optionally send an email for any such openings
      5. Save the current table to cache

    Args:
        raw_records: List of activity dicts (from the API or from fixtures).
        cache_path: Path to the JSON cache file.
        notify: If True (default), send email on openings. Set False for testing.

    Returns:
        The current transformed DataFrame.
    """
    logging.info("Tabularising %d raw records…", len(raw_records))
    curr_df = tabularise(raw_records)

    logging.info("Loading previous rows from cache…")
    prev_df = load_prev_rows(cache_path)

    logging.info("Checking for Wednesday evening openings…")
    opened_keys = wednesday_evening_openings(curr_df, prev_df)

    if opened_keys:
        curr_map = {key_of(row): i for i, row in enumerate(curr_df.to_dicts())}
        opened_indices = [curr_map[k] for k in opened_keys if k in curr_map]

        if opened_indices:
            opened_df = curr_df[opened_indices]

            if notify:
                logging.info("Sending email for %d Wednesday evening opening(s)…", len(opened_keys))
                send_email(
                    f"{len(opened_keys)} Wednesday evening tennis slot(s) opened up",
                    opened_df,
                )
            else:
                logging.info(
                    "Wednesday evening opening(s) detected (%d) but notifications disabled.",
                    len(opened_keys),
                )
        else:
            logging.warning("Opened keys found but no matching rows to display")
    else:
        logging.info("No Wednesday evening openings; no email.")

    logging.info("Saving current rows back to cache…")
    save_rows(cache_path, curr_df)
    return curr_df
