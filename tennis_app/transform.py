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
            "Time24": pl.Utf8,
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
        pl.col("time_24h").alias("Time24"),
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


WEDNESDAY = 2  # datetime.date.weekday(): Monday=0 ... Sunday=6
EVENING_CUTOFF = "19:00"  # zero-padded 24h, so string comparison is safe


def wednesday_evening_openings(curr: pl.DataFrame, prev: pl.DataFrame) -> list[str]:
    """
    Keys of rows that just flipped from booked to free for a Wednesday slot
    starting at or after 19:00.

    "Booked" means zero (or previously unseen) spaces; "free" means spaces > 0.
    """
    if curr.is_empty():
        return []

    prev_map = {key_of(row): row for row in prev.to_dicts()} if not prev.is_empty() else {}

    opened: list[str] = []
    for row in curr.to_dicts():
        date = row.get("Date")
        time24 = row.get("Time24")
        if date is None or time24 is None or date.weekday() != WEDNESDAY or time24 < EVENING_CUTOFF:
            continue

        spaces = row.get("Spaces") or 0
        if spaces <= 0:
            continue

        prev_row = prev_map.get(key_of(row))
        prev_spaces = (prev_row.get("Spaces") if prev_row else None) or 0
        if prev_spaces <= 0:
            opened.append(key_of(row))

    return opened
