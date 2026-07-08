"""Pipeline: the main orchestration that takes raw records and runs the business logic."""

import logging
from typing import Any

import polars as pl

from tennis_app.cache import load_prev_rows, save_rows
from tennis_app.notify import send_email
from tennis_app.transform import diff_tables, key_of, opened_up_keys, tabularise


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
      3. Find watched slots (Wednesday, >=19:00) that flipped booked -> free
      4. Optionally send an email for any such openings
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

    all_changed = diff_tables(curr_df, prev_df)
    logging.info("%d row(s) changed since last poll (informational).", len(all_changed))

    logging.info("Checking watched Wednesday-evening (>=19:00) slots for openings…")
    opened_keys = opened_up_keys(curr_df, prev_df)

    if opened_keys:
        curr_map = {key_of(row): i for i, row in enumerate(curr_df.to_dicts())}
        opened_indices = [curr_map[k] for k in opened_keys if k in curr_map]

        if opened_indices:
            opened_df = curr_df[opened_indices]

            if notify:
                logging.info("Sending email: %d watched slot(s) opened up…", len(opened_keys))
                send_email("Tennis court free: Wednesday evening slot opened up", opened_df)
            else:
                logging.info(
                    "Watched slot(s) opened up (%d) but notifications disabled.", len(opened_keys)
                )
        else:
            logging.warning("Opened keys found but no matching rows to display")
    else:
        logging.info("No watched Wednesday-evening slots opened up; no email.")

    logging.info("Saving current rows back to cache…")
    save_rows(cache_path, curr_df)
    return curr_df
