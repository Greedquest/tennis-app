#!/usr/bin/env python3
import os
import re
import json
import logging
import os
import re
import sys
from email.mime.text import MIMEText
from typing import Any

import requests
import pandas as pd
from redmail import gmail

# ---- config from env ----
DATA_URL = os.getenv("DATA_URL")
CACHE_STATE_PATH = os.getenv("CACHE_STATE_PATH", "cache/state.json")

EMAIL_FROM = os.getenv("EMAIL_FROM", "")  # authorized Gmail address
EMAIL_TO = os.getenv("EMAIL_TO", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")                # Gmail app password

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO), format="%(asctime)s %(levelname)s %(message)s"
)

BOOKING_DATE_RE = re.compile(r"/(\d{4}-\d{2}-\d{2})/")

# Configure Gmail SMTP client at module level
if EMAIL_FROM and APP_PASSWORD:
    gmail.username = EMAIL_FROM
    gmail.password = APP_PASSWORD

# ---------- helpers ----------
def fetch_json(url: str) -> dict[str, Any]:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def extract_iso_date_from_url(url: str) -> str:
    m = BOOKING_DATE_RE.search(url or "")
    return m.group(1) if m else ""


def tabularise(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Mirror your Power Query:
      - iterate rows
      - expand each 'dayXXXX' record
      - expand list 'spaces' -> one output row per item
      - produce tidy dict with keys: Date, Time, Venue, Spaces, Venue Size, Age, Scraped At, URL, venue_id
    """
    out: list[dict[str, Any]] = []
    for row in payload.get("rows", []):
        from_time = row.get("fromTime")
        for k, v in row.items():
            if not str(k).startswith("day"):
                continue
            day_rec = v or {}
            spaces_total = int(day_rec.get("total_spaces", 0))
            for item in day_rec.get("spaces") or []:
                venue_id = int(item.get("venue_id", -1))
                url = item.get("booking_url", "")
                date_iso = extract_iso_date_from_url(url)
                out.append(
                    {
                        "Date": date_iso,
                        "Time": from_time,
                        "Venue": item.get("name", ""),
                        "Spaces": spaces_total,
                        "Venue Size": int(item.get("total_spaces", 0)),
                        "Age": item.get("freshness", ""),
                        "Scraped At": item.get("scraped_at", ""),
                        "URL": url,
                        "venue_id": venue_id,
                    }
                )
    return out


def key_of(r: dict[str, Any]) -> str:
    return f"{r['Date']}|{r['Time']}|{r['venue_id']}"


def load_prev_rows(path: str) -> list[dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.info("No cached state found; starting fresh.")
        return []


def save_rows(path: str, rows: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def diff_tables(curr: list[dict[str, Any]], prev: list[dict[str, Any]]) -> list[str]:
    """
    Compare two tabular lists and return keys whose rows changed.
    'Changed' means any field difference; you can tighten to 'Spaces' only by altering the compare.
    """
    prev_map = {key_of(r): r for r in prev}
    curr_map = {key_of(r): r for r in curr}

    changed_keys: list[str] = []

    # Union of keys: detect adds, updates, removals (if you want removals, include here)
    all_keys = set(prev_map.keys()) | set(curr_map.keys())
    for k in sorted(all_keys):
        a, b = prev_map.get(k), curr_map.get(k)
        if a is None or b is None:
            changed_keys.append(k)  # added or removed
        else:
            # compare selected fields; here full dict equality
            if a != b:
                changed_keys.append(k)

    return changed_keys

# ---------- Gmail SMTP via Red-Mail ----------
def send_email(subject: str, changed_rows: List[Dict[str, Any]]) -> None:
    """
    Send an HTML email with a table of changed tennis court availability.
    
    Red-Mail automatically renders pandas DataFrames as styled HTML tables.
    
    Args:
        subject: Email subject line
        changed_rows: List of row dictionaries that have changed
    """
    if not EMAIL_FROM or not EMAIL_TO:
        raise RuntimeError("EMAIL_FROM/EMAIL_TO not configured")
    
    if not APP_PASSWORD:
        raise RuntimeError("APP_PASSWORD not configured")
    
    if not changed_rows:
        raise ValueError("changed_rows cannot be empty")
    
    # Convert list of dicts to pandas DataFrame
    df = pd.DataFrame(changed_rows)
    
    # Select and reorder columns for display
    display_columns = ["Date", "Time", "Venue", "Spaces", "Venue Size", "URL"]
    df_display = df[display_columns]
    
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
        body_tables={
            "my_table": df_display
        },
        body_params={
            "num_changes": len(changed_rows)
        }
    )
    logging.info("Email sent successfully via SMTP")


# ---------- main ----------
def main() -> int:
    if not DATA_URL:
        raise RuntimeError("DATA_URL environment variable not set")

    logging.info("Fetching JSON …")
    payload = fetch_json(DATA_URL)

    logging.info("Tabularising current payload …")
    curr_rows = tabularise(payload)

    logging.info("Loading previous rows from cache …")
    prev_rows = load_prev_rows(CACHE_STATE_PATH)

    logging.info("Computing changes …")
    changed_keys = diff_tables(curr_rows, prev_rows)

    if changed_keys:
        # Build list of changed rows for the email
        curr_map = {key_of(r): r for r in curr_rows}
        changed_rows = [curr_map[k] for k in changed_keys if k in curr_map]
        
        if changed_rows:  # Only send email if we have actual rows to display
            logging.info("Sending email with %d changed keys …", len(changed_keys))
            send_email("Tennis availability changes", changed_rows)
        else:
            logging.warning("Changed keys found but no matching rows to display")
    else:
        logging.info("No changes detected; no email.")

    logging.info("Saving current rows back to cache …")
    save_rows(CACHE_STATE_PATH, curr_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
