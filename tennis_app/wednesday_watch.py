"""Detect Wednesday-evening slots that just flipped from fully booked to available.

Unlike the general poller (which emails on *any* change to *any* day), this
watches a narrow band — Wednesday, from-time onward — and only fires when a
slot goes from 0 spaces to >0 spaces. A slot going the other way (booked up)
or a brand new listing appearing with 0 spaces is not interesting to us.
"""

import polars as pl

from tennis_app.config import WEDNESDAY_EVENING_MIN_TIME
from tennis_app.transform import key_of

ISO_WEDNESDAY = 3  # pl.Date.dt.weekday(): Monday=1 ... Sunday=7


def filter_wednesday_evening(
    df: pl.DataFrame, min_time: str = WEDNESDAY_EVENING_MIN_TIME
) -> pl.DataFrame:
    """Return only rows that fall on a Wednesday at/after `min_time` (24h "HH:MM")."""
    if df.is_empty() or "Time24" not in df.columns:
        return df.clear()
    return df.filter(
        (pl.col("Date").dt.weekday() == ISO_WEDNESDAY) & (pl.col("Time24") >= min_time)
    )


def find_newly_available_wednesday_evenings(
    curr: pl.DataFrame,
    prev: pl.DataFrame,
    min_time: str = WEDNESDAY_EVENING_MIN_TIME,
) -> pl.DataFrame:
    """
    Return current Wednesday-evening rows whose Spaces went from 0 (or unseen) to >0.

    Args:
        curr: Current transformed DataFrame (see transform.tabularise).
        prev: Previously-cached transformed DataFrame.
        min_time: 24h "HH:MM" cutoff; slots starting before this are ignored.

    Returns:
        Subset of `curr` for newly-available Wednesday-evening slots.
    """
    curr_slots = filter_wednesday_evening(curr, min_time)
    if curr_slots.is_empty():
        return curr_slots

    prev_slots = filter_wednesday_evening(prev, min_time)
    prev_spaces_by_key = {key_of(row): (row.get("Spaces") or 0) for row in prev_slots.to_dicts()}

    rows = curr_slots.to_dicts()
    newly_available = [
        (row.get("Spaces") or 0) > 0 and prev_spaces_by_key.get(key_of(row), 0) == 0 for row in rows
    ]

    return curr_slots.filter(pl.Series(newly_available))
