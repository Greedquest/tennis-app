"""Transform raw API records into a clean Polars DataFrame and diff tables."""

from datetime import UTC, datetime

import polars as pl


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


def _hour_of_12h(time_12h: str) -> int:
    """Parse a 12-hour clock string like '7:00pm' into its 24-hour hour component."""
    return datetime.strptime(time_12h.strip().upper(), "%I:%M%p").hour


def filter_watch_window(df: pl.DataFrame, weekday: int, hour_from: int) -> pl.DataFrame:
    """
    Filter to rows on the given weekday starting at or after hour_from.

    Args:
        df: A tabularised DataFrame (see tabularise()).
        weekday: Python weekday convention, Monday=0 .. Sunday=6.
        hour_from: 24-hour clock hour; rows starting before this are excluded.
    """
    if df.is_empty():
        return df
    return df.filter(
        (pl.col("Date").dt.weekday() == weekday + 1)  # polars: Monday=1 .. Sunday=7
        & (pl.col("Time").map_elements(_hour_of_12h, return_dtype=pl.Int64) >= hour_from)
    )


def newly_available_slots(curr: pl.DataFrame, prev: pl.DataFrame) -> pl.DataFrame:
    """
    Return the rows in curr whose slot flipped from booked (<=0 spaces) to free (>0).

    A row with no matching row in prev (first sighting) is excluded — there's
    no baseline to compare against, so it can't be "newly" free.
    """
    if curr.is_empty() or prev.is_empty():
        return curr.clear()

    prev_map = {key_of(row): row for row in prev.to_dicts()}
    newly_free_rows = []
    for row in curr.to_dicts():
        prior = prev_map.get(key_of(row))
        if prior is None:
            continue
        if (prior.get("Spaces") or 0) <= 0 and (row.get("Spaces") or 0) > 0:
            newly_free_rows.append(row)

    if not newly_free_rows:
        return curr.clear()
    return pl.DataFrame(newly_free_rows, schema=curr.schema)


def diff_tables(curr: pl.DataFrame, prev: pl.DataFrame) -> list[str]:
    """
    Compare two DataFrames and return keys of rows that changed.

    "Changed" means any field difference, or added/removed rows.
    """
    if prev.is_empty():
        return [key_of(row) for row in curr.to_dicts()] if not curr.is_empty() else []

    if curr.is_empty():
        return [key_of(row) for row in prev.to_dicts()]

    prev_map = {key_of(row): row for row in prev.to_dicts()}
    curr_map = {key_of(row): row for row in curr.to_dicts()}

    changed_keys: list[str] = []
    all_keys = sorted(set(prev_map.keys()) | set(curr_map.keys()))
    for k in all_keys:
        a, b = prev_map.get(k), curr_map.get(k)
        if a is None or b is None or a != b:
            changed_keys.append(k)

    return changed_keys
