
#!/usr/bin/env python3
import os
import re
import json
import base64
import logging
import sys
from typing import Any, Dict, List

import requests
from email.mime.text import MIMEText

# Google client libs
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# ---- config from env ----
DATA_URL = os.getenv("DATA_URL")
CACHE_STATE_PATH = os.getenv("CACHE_STATE_PATH", "cache/state.json")

EMAIL_FROM = os.getenv("EMAIL_FROM", "")                    # authorized Gmail address
EMAIL_TO = os.getenv("EMAIL_TO", "")

ACCESS_TOKEN  = os.getenv("ACCESS_TOKEN", "")               # optional (short-lived)
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN", "")              # recommended
CLIENT_ID     = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="%(asctime)s %(levelname)s %(message)s")

BOOKING_DATE_RE = re.compile(r"/(\d{4}-\d{2}-\d{2})/")

# ---------- helpers ----------
def fetch_json(url: str) -> Dict[str, Any]:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()

def extract_iso_date_from_url(url: str) -> str:
    m = BOOKING_DATE_RE.search(url or "")
    return m.group(1) if m else ""

def tabularise(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Mirror your Power Query:
      - iterate rows
      - expand each 'dayXXXX' record
      - expand list 'spaces' -> one output row per item
      - produce tidy dict with keys: Date, Time, Venue, Spaces, Venue Size, Age, Scraped At, URL, venue_id
    """
    out: List[Dict[str, Any]] = []
    for row in payload.get("rows", []):
        from_time = row.get("fromTime")
        for k, v in row.items():
            if not str(k).startswith("day"):
                continue
            day_rec = v or {}
            spaces_total = int(day_rec.get("total_spaces", 0))
            for item in (day_rec.get("spaces") or []):
                venue_id = int(item.get("venue_id", -1))
                url = item.get("booking_url", "")
                date_iso = extract_iso_date_from_url(url)
                out.append({
                    "Date": date_iso,
                    "Time": from_time,
                    "Venue": item.get("name", ""),
                    "Spaces": spaces_total,
                    "Venue Size": int(item.get("total_spaces", 0)),
                    "Age": item.get("freshness", ""),
                    "Scraped At": item.get("scraped_at", ""),
                    "URL": url,
                    "venue_id": venue_id,
                })
    return out

def key_of(r: Dict[str, Any]) -> str:
    return f"{r['Date']}|{r['Time']}|{r['venue_id']}"

def load_prev_rows(path: str) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return tabularise(json.load(f))
    except FileNotFoundError:
        logging.info("No cached state found; starting fresh.")
        return []

def save_rows(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

def diff_tables(curr: List[Dict[str, Any]], prev: List[Dict[str, Any]]) -> List[str]:
    """
    Compare two tabular lists and return keys whose rows changed.
    'Changed' means any field difference; you can tighten to 'Spaces' only by altering the compare.
    """
    prev_map = {key_of(r): r for r in prev}
    curr_map = {key_of(r): r for r in curr}

    changed_keys: List[str] = []

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

# ---------- Gmail via Google client libs ----------
def gmail_credentials() -> Credentials:
    creds = Credentials(
        token=ACCESS_TOKEN or None,
        refresh_token=REFRESH_TOKEN or None,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID or None,
        client_secret=CLIENT_SECRET or None,
        scopes=["https://www.googleapis.com/auth/gmail.send"],  # minimal
    )
    if creds and creds.expired and creds.refresh_token:
        logging.info("Access token expired; refreshing via Google OAuth2.")
        creds.refresh(Request())
    return creds

def send_email(subject: str, body: str) -> str:
    if not EMAIL_FROM or not EMAIL_TO:
        raise RuntimeError("EMAIL_FROM/EMAIL_TO not configured")

    creds = gmail_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    msg = MIMEText(body, _charset="utf-8")
    msg["to"] = EMAIL_TO
    msg["from"] = EMAIL_FROM
    msg["subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()  # Gmail users.messages.send
    return sent.get("id", "")

# ---------- main ----------
def main() -> int:
    logging.info("Fetching JSON …")
    payload = fetch_json(DATA_URL)

    logging.info("Tabularising current payload …")
    curr_rows = tabularise(payload)

    logging.info("Loading previous rows from cache …")
    prev_rows = load_prev_rows(CACHE_STATE_PATH)

    logging.info("Computing changes …")
    changed_keys = diff_tables(curr_rows, prev_rows)

    if changed_keys:
        body = "\n".join(changed_keys)
        logging.info("Sending email with %d changed keys …", len(changed_keys))
        msg_id = send_email("Tennis availability changes", body)
        logging.info("Email sent. Message ID: %s", msg_id)
    else:
        logging.info("No changes detected; no email.")

    logging.info("Saving current rows back to cache …")
    save_rows(CACHE_STATE_PATH, curr_rows)
    return 0

if __name__ == "__main__":
    sys.exit(main())
