"""Transform raw API records into a clean Polars DataFrame and diff tables."""

from datetime import UTC, datetime

import polars as pl

WEDNESDAY_ISOWEEKDAY = 3


def tabularise(raw_records: list[dict]) -> pl.DataFrame:
    """
    Transform raw API activity records into a normalised Polars DataFrame.

    Accepts the list of dicts returned by fetch_all_activities() (or loaded
    from a fixture file).  Each dict has nested objects for starts_at,
    ends_at, and price which are flattened here.

    Returns a DataFrame with columns:
        Time, Date, Spaces, Venue, Venue Size, Age, Scraped At, URL
    """
    empty = pl.DataFrame(
        schema={
            "Time": pl.Utf8,
            "Date": pl.Date,
            "Spaces": pl.Int64,
            "Venue": pl.Utf8,
            "Venue Size": pl.Utf8,
            "Age": pl.Utf8,
            "Scraped At": pl.Datetime,
            "URL": pl.Utf8,
        }
    )
    if not raw_records:
        return empty

    # Flatten nested dicts before creating the DataFrame
    flat: list[dict] = []
    for rec in raw_records:
        starts_at = rec.get("starts_at") or {}
        ends_at = rec.get("ends_at") or {}
        flat.append(
            {
                "time_12h": starts_at.get("format_12_hour"),
                "time_24h": starts_at.get("format_24_hour"),
                "end_24h": ends_at.get("format_24_hour"),
                "date": rec.get("date"),
                "spaces": rec.get("spaces"),
                "location": rec.get("location"),
                "timestamp": rec.get("timestamp"),
                "venue": rec.get("venue"),
                "court": rec.get("court"),
            }
        )

    df = pl.DataFrame(flat)

    result = df.select(
        pl.col("time_12h").alias("Time"),
        pl.col("date").str.strptime(pl.Date, "%Y-%m-%d", strict=False).alias("Date"),
        pl.col("spaces").cast(pl.Int64).alias("Spaces"),
        pl.col("location").alias("Venue"),
        pl.lit(None).cast(pl.Utf8).alias("Venue Size"),
        pl.lit(None).cast(pl.Utf8).alias("Age"),
        pl.col("timestamp")
        .cast(pl.Int64)
        .map_elements(
            lambda ts: datetime.fromtimestamp(ts, tz=UTC) if ts is not None else None,
            return_dtype=pl.Datetime("us", "UTC"),
        )
        .cast(pl.Datetime("us"))
        .alias("Scraped At"),
        # Construct booking URL
        (
            pl.lit("https://bookings.better.org.uk/location/")
            + pl.col("venue")
            + pl.lit("/")
            + pl.col("court")
            + pl.lit("/")
            + pl.col("date")
            + pl.lit("/by-time/slot/")
            + pl.col("time_24h")
            + pl.lit("-")
            + pl.col("end_24h")
        ).alias("URL"),
    )

    return result


def key_of(row: dict) -> str:
    """Generate a unique key for a row dict based on Date|Time|Venue."""
    date_str = str(row.get("Date", ""))
    time_str = str(row.get("Time", ""))
    venue_str = str(row.get("Venue", ""))
    return f"{date_str}|{time_str}|{venue_str}"


def filter_wednesday_evening(raw_records: list[dict], min_hour: int = 19) -> list[dict]:
    """
    Keep only raw activity records for Wednesday slots starting at/after ``min_hour``.

    Reads ``date`` (YYYY-MM-DD) and ``starts_at.format_24_hour`` (HH:MM) directly off
    the raw record, ahead of tabularise(), so the stable output schema is untouched.
    """
    kept: list[dict] = []
    for rec in raw_records:
        date_str = rec.get("date")
        time_24h = (rec.get("starts_at") or {}).get("format_24_hour")
        if not date_str or not time_24h:
            continue
        try:
            is_wednesday = datetime.strptime(date_str, "%Y-%m-%d").isoweekday() == WEDNESDAY_ISOWEEKDAY
            hour = int(time_24h.split(":", 1)[0])
        except (ValueError, IndexError):
            continue
        if is_wednesday and hour >= min_hour:
            kept.append(rec)
    return kept


def diff_booked_to_free(curr: pl.DataFrame, prev: pl.DataFrame) -> list[str]:
    """
    Compare two DataFrames and return keys of rows that flipped from fully
    booked (0 spaces) to free (>0 spaces). Rows absent from either side, and
    rows that were already free or stayed booked, are not reported.
    """
    if prev.is_empty() or curr.is_empty():
        return []

    prev_map = {key_of(row): row for row in prev.to_dicts()}
    curr_map = {key_of(row): row for row in curr.to_dicts()}

    opened_keys: list[str] = []
    for k, curr_row in curr_map.items():
        prev_row = prev_map.get(k)
        if prev_row is None:
            continue
        prev_spaces = prev_row.get("Spaces") or 0
        curr_spaces = curr_row.get("Spaces") or 0
        if prev_spaces == 0 and curr_spaces > 0:
            opened_keys.append(k)

    return opened_keys
