"""Pipeline: the main orchestration that takes raw records and runs the business logic."""

import logging
from typing import Any

import polars as pl

from tennis_app.cache import load_prev_rows, save_rows
from tennis_app.notify import send_email
from tennis_app.transform import diff_tables, key_of, tabularise


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
      3. Diff the two
      4. Optionally send an email for any changes
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

    logging.info("Computing changes…")
    changed_keys = diff_tables(curr_df, prev_df)

    if changed_keys:
        curr_map = {key_of(row): i for i, row in enumerate(curr_df.to_dicts())}
        changed_indices = [curr_map[k] for k in changed_keys if k in curr_map]

        if changed_indices:
            changed_df = curr_df[changed_indices]

            if notify:
                logging.info("Sending email with %d changed keys…", len(changed_keys))
                send_email("Tennis availability changes", changed_df)
            else:
                logging.info("Changes detected (%d) but notifications disabled.", len(changed_keys))
        else:
            logging.warning("Changed keys found but no matching rows to display")
    else:
        logging.info("No changes detected; no email.")

    logging.info("Saving current rows back to cache…")
    save_rows(cache_path, curr_df)
    return curr_df
