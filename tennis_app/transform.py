"""Transform raw API records into a clean Polars DataFrame and diff tables."""

import logging
from datetime import UTC, date, datetime

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


def _start_hour(rec: dict) -> int | None:
    """Extract the integer start hour from a raw record's starts_at.format_24_hour."""
    starts_at = rec.get("starts_at") or {}
    hhmm = starts_at.get("format_24_hour")
    if not isinstance(hhmm, str) or ":" not in hhmm:
        return None
    try:
        return int(hhmm.split(":", 1)[0])
    except ValueError:
        return None


def filter_target_records(
    raw_records: list[dict],
    *,
    weekday: int,
    min_hour: int,
    on_date: date | None = None,
) -> list[dict]:
    """
    Keep only the slots we care about: a given weekday, at/after ``min_hour``.

    Per the brief we watch Wednesday (weekday=2) evening slots (start >= 19:00).
    When ``on_date`` is given, restrict further to that exact date — used to
    pin the poll to *this* Wednesday's slots rather than every Wednesday in the
    fetched window.
    """
    target: list[dict] = []
    for rec in raw_records:
        date_str = rec.get("date")
        if not isinstance(date_str, str):
            continue
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d.weekday() != weekday:
            continue
        if on_date is not None and d != on_date:
            continue
        hour = _start_hour(rec)
        if hour is None or hour < min_hour:
            continue
        target.append(rec)
    return target


def key_of(row: dict) -> str:
    """
    Generate a unique key for a slot.

    Prefer the booking URL, which encodes venue+court+date+time and so
    distinguishes two venues whose ``location`` label is identical (both
    Highbury Fields and Islington outdoor report ``location`` = "Multiple",
    which would otherwise collide on Date|Time|Venue). Fall back to
    Date|Time|Venue when no URL is present.
    """
    url = row.get("URL")
    if url:
        return str(url)
    date_str = str(row.get("Date", ""))
    time_str = str(row.get("Time", ""))
    venue_str = str(row.get("Venue", ""))
    return f"{date_str}|{time_str}|{venue_str}"


def _spaces(row: dict) -> int:
    """Coerce a row's Spaces value to an int (missing/None -> 0)."""
    val = row.get("Spaces")
    try:
        return int(val) if val is not None else 0
    except (TypeError, ValueError):
        return 0


def newly_free(curr: pl.DataFrame, prev: pl.DataFrame) -> pl.DataFrame:
    """
    Return the subset of ``curr`` rows that just transitioned booked -> free.

    A slot fires an alert only when it was previously seen as *booked*
    (0 spaces) and is now *free* (>=1 space).  Slots that are newly seen with
    no prior record do NOT fire — we can't know they "opened up", and this
    avoids a flood on the first ever run.  This is stricter, and more correct
    for the brief ("On any slot moving from booked to free"), than a plain
    field-level diff.
    """
    if curr.is_empty():
        return curr

    prev_spaces = {key_of(row): _spaces(row) for row in prev.to_dicts()}

    changed_indices: list[int] = []
    for i, row in enumerate(curr.to_dicts()):
        k = key_of(row)
        was = prev_spaces.get(k)
        if was is not None and was == 0 and _spaces(row) > 0:
            changed_indices.append(i)

    if not changed_indices:
        return curr.clear()

    logging.debug("newly_free: %d slot(s) went booked -> free", len(changed_indices))
    return curr[changed_indices]
