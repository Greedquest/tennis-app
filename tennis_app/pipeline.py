"""Pipeline: the main orchestration that takes raw records and runs the business logic.

Wednesday-evening court watch: alert only when a slot starting >= WEDNESDAY_MIN_HOUR
on Wednesday flips from fully booked (0 spaces) to free (>0 spaces). See CLAUDE.md.
"""

import logging
from typing import Any

import polars as pl

from tennis_app.cache import load_prev_rows, save_rows
from tennis_app.notify import send_email
from tennis_app.transform import diff_booked_to_free, filter_wednesday_evening, key_of, tabularise

WEDNESDAY_MIN_HOUR = 19


def run(
    raw_records: list[dict[str, Any]],
    cache_path: str,
    *,
    notify: bool = True,
) -> pl.DataFrame:
    """
    Execute the Wednesday-evening watch pipeline:
      1. Filter to Wednesday slots starting >= WEDNESDAY_MIN_HOUR
      2. Transform into a clean table
      3. Load the previously-cached table
      4. Find slots that flipped from fully booked to free
      5. Optionally send an email for any such slots
      6. Save the current table to cache

    Args:
        raw_records: List of activity dicts (from the API or from fixtures).
        cache_path: Path to the JSON cache file.
        notify: If True (default), send email on changes. Set False for testing.

    Returns:
        The current transformed DataFrame (Wednesday-evening slots only).
    """
    logging.info(
        "Filtering %d raw records to Wednesday >=%d:00…", len(raw_records), WEDNESDAY_MIN_HOUR
    )
    wednesday_records = filter_wednesday_evening(raw_records, min_hour=WEDNESDAY_MIN_HOUR)

    logging.info("Tabularising %d Wednesday-evening records…", len(wednesday_records))
    curr_df = tabularise(wednesday_records)

    logging.info("Loading previous rows from cache…")
    prev_df = load_prev_rows(cache_path)

    logging.info("Computing booked-to-free flips…")
    opened_keys = diff_booked_to_free(curr_df, prev_df)

    if opened_keys:
        curr_map = {key_of(row): i for i, row in enumerate(curr_df.to_dicts())}
        opened_indices = [curr_map[k] for k in opened_keys if k in curr_map]

        if opened_indices:
            opened_df = curr_df[opened_indices]

            if notify:
                logging.info("Sending email for %d newly-free Wednesday evening slot(s)…", len(opened_keys))
                send_email(
                    "Tennis court free: Wednesday evening",
                    opened_df,
                    heading="Wednesday Evening Slot Opened Up",
                )
            else:
                logging.info(
                    "%d Wednesday-evening slot(s) opened up but notifications disabled.",
                    len(opened_keys),
                )
        else:
            logging.warning("Opened keys found but no matching rows to display")
    else:
        logging.info("No Wednesday-evening slots opened up; no email.")

    logging.info("Saving current rows back to cache…")
    save_rows(cache_path, curr_df)
    return curr_df
