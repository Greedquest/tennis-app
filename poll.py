#!/usr/bin/env python3
import logging
import os
import sys
from typing import Any

import pandas as pd
import requests
from redmail import gmail

# ---- config from env ----
DATA_URL = os.getenv("DATA_URL")
CACHE_STATE_PATH = os.getenv("CACHE_STATE_PATH", "cache/state.json")

EMAIL_FROM = os.getenv("EMAIL_FROM", "")  # authorized Gmail address
EMAIL_TO = os.getenv("EMAIL_TO", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")  # Gmail app password

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO), format="%(asctime)s %(levelname)s %(message)s"
)

# Configure Gmail SMTP client at module level
if EMAIL_FROM and APP_PASSWORD:
    gmail.username = EMAIL_FROM
    gmail.password = APP_PASSWORD


# ---------- helpers ----------
def fetch_json(url: str) -> dict[str, Any]:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def tabularise(payload: dict[str, Any]) -> pd.DataFrame:
    """
    Mirror Power Query transformation:
      1. Convert rows to table
      2. Unpivot other columns (keep hour, fromTime; unpivot day* columns)
      3. Expand Value record (day, total_spaces, spaces)
      4. Expand spaces list
      5. Expand spaces record fields
      6. Change column types
      7. Rename and remove columns

    Returns DataFrame with columns: Time, Date, Spaces, Venue, Venue Size, Age, Scraped At, URL
    """
    # Step 1: Convert rows to DataFrame
    rows_df = pd.DataFrame(payload.get("rows", []))

    if rows_df.empty:
        return pd.DataFrame(
            columns=["Time", "Date", "Spaces", "Venue", "Venue Size", "Age", "Scraped At", "URL"]
        )

    # Step 2: Identify columns to keep (id_cols) and columns to unpivot (day_cols)
    # According to Power Query: keep hour and fromTime, unpivot all other columns
    id_cols = ["hour", "fromTime"]
    day_cols = [col for col in rows_df.columns if col not in id_cols]

    # Step 3: Unpivot (melt) the day columns
    unpivoted = rows_df.melt(
        id_vars=id_cols, value_vars=day_cols, var_name="Attribute", value_name="Value"
    )

    # Step 4: Drop rows where Value is None
    unpivoted = unpivoted.dropna(subset=["Value"])

    if unpivoted.empty:
        return pd.DataFrame(
            columns=["Time", "Date", "Spaces", "Venue", "Venue Size", "Age", "Scraped At", "URL"]
        )

    # Step 5: Expand the Value column (dict with day, total_spaces, spaces)
    value_expanded = pd.json_normalize(unpivoted["Value"].tolist())
    result = pd.concat(
        [unpivoted.drop(columns=["Value"]).reset_index(drop=True), value_expanded], axis=1
    )

    # Step 6: Filter out rows with empty spaces arrays to avoid NaN values
    result = result[result["spaces"].apply(lambda x: len(x) > 0 if isinstance(x, list) else False)]

    if result.empty:
        return pd.DataFrame(
            columns=["Time", "Date", "Spaces", "Venue", "Venue Size", "Age", "Scraped At", "URL"]
        )

    result = result.reset_index(drop=True)

    # Step 7: Expand the spaces list column
    result = result.explode("spaces").reset_index(drop=True)

    # Step 8: Expand spaces record
    spaces_expanded = pd.json_normalize(result["spaces"].tolist())
    result = pd.concat(
        [result.drop(columns=["spaces"]).reset_index(drop=True), spaces_expanded], axis=1
    )

    # Handle duplicate 'total_spaces' columns by renaming them
    # First total_spaces is from Value (day total), second is from spaces (venue total)
    cols = result.columns.tolist()
    new_cols = []
    total_spaces_count = 0
    for col in cols:
        if col == "total_spaces":
            if total_spaces_count == 0:
                new_cols.append("Value.total_spaces")
            else:
                new_cols.append("Value.spaces.total_spaces")
            total_spaces_count += 1
        else:
            new_cols.append(col)
    result.columns = pd.Index(new_cols)

    # Step 9: Apply type conversions (matching Power Query)
    # Note: hour, venue_id, and Attribute are not converted since they will be dropped in Step 11
    result["fromTime"] = pd.to_datetime(result["fromTime"], format="%H:%M", errors="coerce").dt.time

    # Parse dates with year inference from booking_url
    # The day column has format "DD MMM" (e.g., "30 Dec", "01 Jan")
    # Extract year from booking_url which contains full date like "2026-01-02"
    def parse_date_with_year(row):
        day_str = row["day"]
        booking_url = row.get("booking_url", "")

        # Try to extract year from booking_url
        import re

        match = re.search(r"/(\d{4})-(\d{2})-(\d{2})/", booking_url)
        if match:
            year = match.group(1)
            # Parse with extracted year
            date_str = f"{day_str} {year}"
            return pd.to_datetime(date_str, format="%d %b %Y", errors="coerce")
        else:
            # Fallback: try to infer year based on current date
            # If we can't extract from URL, parse without year and pandas will use current year
            return pd.to_datetime(day_str, format="%d %b", errors="coerce")

    result["day"] = result.apply(parse_date_with_year, axis=1).dt.date
    result["scraped_at"] = pd.to_datetime(result["scraped_at"], errors="coerce")

    # Step 10: Rename columns (first rename)
    result = result.rename(
        columns={"fromTime": "Time", "day": "Date", "Value.total_spaces": "Spaces"}
    )

    # Step 11: Remove columns (venue_id, hour, Attribute)
    result = result.drop(columns=["venue_id", "hour", "Attribute"])

    # Step 12: Rename columns (second rename)
    result = result.rename(
        columns={
            "name": "Venue",
            "Value.spaces.total_spaces": "Venue Size",
            "freshness": "Age",
            "scraped_at": "Scraped At",
            "booking_url": "URL",
        }
    )

    # Reorder columns to match Power Query output
    final_columns = ["Time", "Date", "Spaces", "Venue", "Venue Size", "Age", "Scraped At", "URL"]
    return result[final_columns]


def key_of(row: pd.Series) -> str:
    """Generate a unique key for a DataFrame row based on Date, Time, and Venue."""
    # Convert time object to string format for consistent key generation
    time_str = str(row["Time"]) if pd.notna(row["Time"]) else ""
    date_str = str(row["Date"]) if pd.notna(row["Date"]) else ""
    venue_str = str(row["Venue"]) if pd.notna(row["Venue"]) else ""
    return f"{date_str}|{time_str}|{venue_str}"


def load_prev_rows(path: str) -> pd.DataFrame:
    """Load previously cached DataFrame from JSON file."""
    try:
        with open(path, encoding="utf-8") as f:
            df = pd.read_json(f, orient="records")
        # Convert columns to appropriate types with error handling
        if not df.empty:
            if "Time" in df.columns:
                df["Time"] = pd.to_datetime(df["Time"], format="%H:%M:%S", errors="coerce").dt.time
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
            if "Scraped At" in df.columns:
                df["Scraped At"] = pd.to_datetime(df["Scraped At"], errors="coerce")
        return df
    except FileNotFoundError:
        logging.info("No cached state found; starting fresh.")
        return pd.DataFrame(
            columns=["Time", "Date", "Spaces", "Venue", "Venue Size", "Age", "Scraped At", "URL"]
        )


def save_rows(path: str, df: pd.DataFrame) -> None:
    """Save DataFrame to JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    # Convert to records for JSON serialization
    df.to_json(tmp, orient="records", date_format="iso", indent=2)
    os.replace(tmp, path)


def diff_tables(curr: pd.DataFrame, prev: pd.DataFrame) -> list[str]:
    """
    Compare two DataFrames and return keys of rows that changed.
    'Changed' means any field difference or added/removed rows.
    """
    if prev.empty:
        # All current rows are new
        return curr.apply(key_of, axis=1).tolist() if not curr.empty else []

    if curr.empty:
        # All previous rows were removed
        return prev.apply(key_of, axis=1).tolist()

    # Create dictionaries keyed by row key
    prev_map = {key_of(row): row.to_dict() for _, row in prev.iterrows()}
    curr_map = {key_of(row): row.to_dict() for _, row in curr.iterrows()}

    changed_keys: list[str] = []

    # Union of keys: detect adds, updates, removals
    all_keys = set(prev_map.keys()) | set(curr_map.keys())
    for k in sorted(all_keys):
        a, b = prev_map.get(k), curr_map.get(k)
        if a is None or b is None:
            changed_keys.append(k)  # added or removed
        else:
            # Compare row values
            if a != b:
                changed_keys.append(k)

    return changed_keys


# ---------- Gmail SMTP via Red-Mail ----------
def send_email(subject: str, changed_rows: pd.DataFrame) -> None:
    """
    Send an HTML email with a table of changed tennis court availability.

    Red-Mail automatically renders pandas DataFrames as styled HTML tables.

    Args:
        subject: Email subject line
        changed_rows: DataFrame of rows that have changed
    """
    if not EMAIL_FROM or not EMAIL_TO:
        raise RuntimeError("EMAIL_FROM/EMAIL_TO not configured")

    if not APP_PASSWORD:
        raise RuntimeError("APP_PASSWORD not configured")

    if changed_rows.empty:
        raise ValueError("changed_rows cannot be empty")

    # Select and reorder columns for display
    display_columns = ["Date", "Time", "Venue", "Spaces", "Venue Size", "URL"]
    df_display = changed_rows[display_columns]

    # Simple HTML with insertion point for table - Red-Mail handles styling
    gmail.send(
        sender=EMAIL_FROM,
        receivers=[EMAIL_TO],
        subject=subject,
        html="""
        <h2>Tennis Court Availability Changes</h2>
        <p>{{ num_changes }} availability change(s) detected:</p>
        {{ my_table }}
        """,
        body_tables={"my_table": df_display},
        body_params={"num_changes": len(changed_rows)},
    )
    logging.info("Email sent successfully via SMTP")


# ---------- main ----------
def main() -> int:
    if not DATA_URL:
        raise RuntimeError("DATA_URL environment variable not set")

    logging.info("Fetching JSON …")
    payload = fetch_json(DATA_URL)

    logging.info("Tabularising current payload …")
    curr_df = tabularise(payload)

    logging.info("Loading previous rows from cache …")
    prev_df = load_prev_rows(CACHE_STATE_PATH)

    logging.info("Computing changes …")
    changed_keys = diff_tables(curr_df, prev_df)

    if changed_keys:
        # Build DataFrame of changed rows for the email
        curr_map = {key_of(row): idx for idx, row in curr_df.iterrows()}
        changed_indices = [curr_map[k] for k in changed_keys if k in curr_map]
        changed_df = curr_df.loc[changed_indices]

        if not changed_df.empty:  # Only send email if we have actual rows to display
            logging.info("Sending email with %d changed keys …", len(changed_keys))
            send_email("Tennis availability changes", changed_df)
        else:
            logging.warning("Changed keys found but no matching rows to display")
    else:
        logging.info("No changes detected; no email.")

    logging.info("Saving current rows back to cache …")
    save_rows(CACHE_STATE_PATH, curr_df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
