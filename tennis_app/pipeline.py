"""Pipeline: the main orchestration that takes raw records and runs the business logic."""

import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl

from tennis_app.cache import load_prev_rows, save_rows
from tennis_app.config import (
    POLL_END_HOUR,
    POLL_START_HOUR,
    TARGET_MIN_HOUR,
    TARGET_WEEKDAY,
    TZ_NAME,
)
from tennis_app.notify import send_email
from tennis_app.transform import filter_target_records, newly_free, tabularise


def within_poll_window(now: datetime) -> bool:
    """
    True when ``now`` (local time) is on the target weekday inside the poll window.

    The brief runs the monitor on Wednesdays from midday to 22:00.  The GitHub
    Actions cron gates coarsely in UTC; this is the precise, DST-aware gate so a
    stray dispatch outside the window is a quiet no-op instead of a spurious poll.
    """
    return now.weekday() == TARGET_WEEKDAY and POLL_START_HOUR <= now.hour < POLL_END_HOUR


def run(
    raw_records: list[dict[str, Any]],
    cache_path: str,
    *,
    notify: bool = True,
    now: datetime | None = None,
    enforce_window: bool = True,
) -> pl.DataFrame:
    """
    Execute the full pipeline:
      1. (optional) Bail out quietly if outside the Wed midday-22:00 window.
      2. Filter raw records to this Wednesday's slots starting >= 19:00.
      3. Transform them into a clean table.
      4. Load the previously-cached table and detect booked -> free transitions.
      5. Email an alert for any slot that just opened up.
      6. Save the current table to cache.

    Args:
        raw_records: List of activity dicts (from the API or from fixtures).
        cache_path: Path to the JSON cache file.
        notify: If True (default), send email on openings. Set False for testing.
        now: Current local time; defaults to now in the configured timezone.
        enforce_window: If True (default), skip work outside the poll window.

    Returns:
        The current transformed DataFrame of target slots (may be empty).
    """
    tz = ZoneInfo(TZ_NAME)
    now = now or datetime.now(tz)
    today: date = now.date()

    if enforce_window and not within_poll_window(now):
        logging.info(
            "Outside poll window (%s, weekday=%d, hour=%d); nothing to do.",
            now.isoformat(timespec="minutes"),
            now.weekday(),
            now.hour,
        )
        return tabularise([])

    target_records = filter_target_records(
        raw_records,
        weekday=TARGET_WEEKDAY,
        min_hour=TARGET_MIN_HOUR,
        on_date=today,
    )
    logging.info(
        "Checked %d raw record(s); %d are target slots (%s, start >= %02d:00).",
        len(raw_records),
        len(target_records),
        today.isoformat(),
        TARGET_MIN_HOUR,
    )

    curr_df = tabularise(target_records)
    prev_df = load_prev_rows(cache_path)

    opened = newly_free(curr_df, prev_df)

    if opened.is_empty():
        free_now = int((curr_df["Spaces"] > 0).sum()) if not curr_df.is_empty() else 0
        logging.info("No new openings (%d slot(s) currently free). No alert.", free_now)
    else:
        logging.info("%d slot(s) just opened up — sending alert.", opened.height)
        if notify:
            send_email("🎾 Wednesday evening court just opened up", opened)
        else:
            logging.info("Notifications disabled; skipping email.")

    save_rows(cache_path, curr_df)
    return curr_df
