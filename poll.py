#!/usr/bin/env python3
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests
from redmail import gmail

# ---- config from env ----
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


# Venue/Court combinations to poll
VENUES = [
    {"venue": "islington-tennis-centre", "court": "tennis-court-indoor"},
    {"venue": "islington-tennis-centre", "court": "tennis-court-outdoor"},
]


# ---------- helpers ----------
def fetch_activities(venue: str, court: str, date: str) -> list[dict[str, Any]]:
    """
    Fetch activity data from the Better Admin API for a specific venue, court, and date.

    Args:
        venue: Venue identifier (e.g., "islington-tennis-centre")
        court: Court/activity identifier (e.g., "tennis-court-indoor")
        date: Date in YYYY-MM-DD format

    Returns:
        List of activity records
    """
    url = f"https://better-admin.org.uk/api/activities/venue/{venue}/activity/{court}/times"
    headers = {"Origin": "https://bookings.better.org.uk"}
    params = {"date": date}

    r = requests.get(url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    response_data = r.json()

    # Extract data array from response
    return response_data.get("data", [])


def fetch_all_activities() -> pd.DataFrame:
    """
    Fetch activities for all venue/court combinations and the next 5 days.

    Returns:
        DataFrame with all fetched activities
    """
    # Generate dates for next 5 days
    today = datetime.now().date()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]

    all_records = []
    for venue_court in VENUES:
        venue = venue_court["venue"]
        court = venue_court["court"]

        for date in dates:
            try:
                logging.info(f"Fetching {venue}/{court} for {date}...")
                activities = fetch_activities(venue, court, date)

                # Add venue and court info to each record
                for activity in activities:
                    activity["venue"] = venue
                    activity["court"] = court
                    all_records.append(activity)

            except Exception as e:
                logging.warning(f"Failed to fetch {venue}/{court} for {date}: {e}")
                continue

    if not all_records:
        return pd.DataFrame(
            columns=["Time", "Date", "Spaces", "Venue", "Venue Size", "Age", "Scraped At", "URL"]
        )

    return pd.DataFrame(all_records)


def tabularise(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform the raw API data into the expected output format.

    The API returns records with:
    - starts_at, ends_at: time strings
    - duration: duration value
    - price: price value
    - timestamp: Unix timestamp
    - date: date string
    - location: location name
    - spaces: number of available spaces

    Returns DataFrame with columns: Time, Date, Spaces, Venue, Venue Size, Age, Scraped At, URL
    """
    if df.empty:
        return pd.DataFrame(
            columns=["Time", "Date", "Spaces", "Venue", "Venue Size", "Age", "Scraped At", "URL"]
        )

    # Create a copy to avoid mutating the input DataFrame
    df = df.copy()

    # Convert timestamp from Unix epoch to datetime
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")

    # Parse starts_at to get time
    if "starts_at" in df.columns:
        df["Time"] = pd.to_datetime(df["starts_at"], format="%H:%M", errors="coerce").dt.time

    # Parse date
    if "date" in df.columns:
        df["Date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    # Rename and select columns
    result = pd.DataFrame()
    result["Time"] = df.get("Time")
    result["Date"] = df.get("Date")
    result["Spaces"] = df.get("spaces")
    result["Venue"] = df.get("location", df.get("venue"))
    result["Venue Size"] = None  # Not available in new API (old API had total_spaces)
    result["Age"] = None  # Not available in new API
    result["Scraped At"] = df.get("timestamp")

    # Construct URL from venue, court, date, and time
    def construct_url(row):
        if (
            pd.isna(row.get("venue"))
            or pd.isna(row.get("court"))
            or pd.isna(row.get("Date"))
            or pd.isna(row.get("Time"))
        ):
            return None
        venue = row["venue"]
        court = row["court"]
        date_str = (
            row["Date"].strftime("%Y-%m-%d")
            if hasattr(row["Date"], "strftime")
            else str(row["Date"])
        )
        time_str = (
            row["Time"].strftime("%H:%M") if hasattr(row["Time"], "strftime") else str(row["Time"])
        )
        # Construct URL similar to the booking_url pattern
        return f"https://bookings.better.org.uk/location/{venue}/{court}/{date_str}/by-time/slot/{time_str}"

    # Add venue and court from original df for URL construction
    result["venue"] = df.get("venue")
    result["court"] = df.get("court")
    result["URL"] = result.apply(construct_url, axis=1)

    # Drop temporary columns
    result = result.drop(columns=["venue", "court"])

    # Reorder columns to match expected output
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
    logging.info("Fetching activities from Better Admin API...")
    raw_df = fetch_all_activities()

    logging.info("Tabularising current payload …")
    curr_df = tabularise(raw_df)

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
