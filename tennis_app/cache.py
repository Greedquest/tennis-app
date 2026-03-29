"""Load and save cached state as JSON using Polars."""

import logging
import os

import polars as pl

EXPECTED_SCHEMA = {
    "Time": pl.Utf8,
    "Date": pl.Date,
    "Spaces": pl.Int64,
    "Venue": pl.Utf8,
    "Venue Size": pl.Utf8,
    "Age": pl.Utf8,
    "Scraped At": pl.Datetime,
    "URL": pl.Utf8,
}


def _empty_frame() -> pl.DataFrame:
    return pl.DataFrame(schema=EXPECTED_SCHEMA)


def load_prev_rows(path: str) -> pl.DataFrame:
    """Load previously cached DataFrame from a JSON file."""
    try:
        df = pl.read_json(path)
        if df.is_empty():
            return _empty_frame()
        # Cast columns to expected types (read_json returns strings for dates)
        if "Date" in df.columns:
            df = df.with_columns(pl.col("Date").str.strptime(pl.Date, "%Y-%m-%d", strict=False))
        if "Scraped At" in df.columns:
            df = df.with_columns(
                pl.col("Scraped At").str.strptime(
                    pl.Datetime("us"), "%Y-%m-%d %H:%M:%S", strict=False
                )
            )
        if "Spaces" in df.columns:
            df = df.with_columns(pl.col("Spaces").cast(pl.Int64, strict=False))
        # Ensure nullable string columns have the right type
        for col_name in ("Venue Size", "Age"):
            if col_name in df.columns and df.schema[col_name] == pl.Null:
                df = df.with_columns(pl.col(col_name).cast(pl.Utf8))
        return df
    except FileNotFoundError:
        logging.info("No cached state found; starting fresh.")
        return _empty_frame()


def save_rows(path: str, df: pl.DataFrame) -> None:
    """Save DataFrame to JSON file (atomic write via temp file)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    df.write_json(tmp)
    os.replace(tmp, path)
