"""Local Wednesday-evening court watch.

Alerts (desktop/Termux notification only -- no booking automation) the moment a slot
starting at or after 19:00 on Wednesday flips from booked to free.

This is deliberately separate from the cloud pipeline (tennis_app/pipeline.py, driven by
.github/workflows/poller.yml + Gmail SMTP). That pipeline polls better-admin.org.uk every
minute and emails on any change for Islington Tennis Centre. This module targets a
different source -- the localtenniscourts.com aggregator -- for a tighter Wednesday-only
alert, and is meant to run as a *local* cron/Termux job: Claude Code routines are
hourly-minimum, too coarse for 5-minute Wednesday-only polling.

IMPORTANT -- unverified data source: this development sandbox's outbound network blocks
localtenniscourts.com (same as it blocks better-admin.org.uk; see CLAUDE.md gotchas), so
the parsing heuristics below have never been checked against a real response. Run
scripts/probe_localtenniscourts.py somewhere with real egress (e.g. a throwaway GitHub
Actions push, per the existing repo convention for better-admin.org.uk) before relying on
this, and adjust extract_slots()/normalise_slot() if the real payload shape differs.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, time

import requests
from bs4 import BeautifulSoup

DEFAULT_URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

WEDNESDAY = 2  # datetime.weekday(): Monday=0 ... Sunday=6
MIN_HOUR = 19  # only watch slots starting at or after 19:00

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
}

# Candidate patterns for server-rendered "hydration" state blobs, in rough order of how
# common they are among JS-framework sites. Unverified against the real page -- see
# module docstring.
EMBEDDED_JSON_PATTERNS = [
    re.compile(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S),
    re.compile(r"window\.__NUXT__\s*=\s*(\{.*?\})\s*;?\s*</script>", re.S),
    re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>", re.S),
]

_SLOT_KEY_HINTS = {"date", "start", "start_time", "time", "status", "available", "spaces", "booked"}
_STATUS_FREE_WORDS = {"available", "free", "open", "book now", "book"}
_STATUS_BOOKED_WORDS = {"booked", "full", "unavailable", "closed"}
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


class SlotParseError(RuntimeError):
    """Raised when no recognisable slot data could be found in a fetched page."""


@dataclass(frozen=True)
class Slot:
    start: datetime
    venue: str
    court: str
    status: str  # "free" or "booked"
    raw: dict


def fetch_html(url: str = DEFAULT_URL) -> str:
    """Fetch the aggregator page. Raises requests.HTTPError on non-2xx."""
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.text


def _walk_for_slot_dicts(obj: object) -> list[dict]:
    found: list[dict] = []
    if isinstance(obj, dict):
        keys = {str(k).lower() for k in obj}
        if len(keys & _SLOT_KEY_HINTS) >= 2:
            found.append(obj)
        for v in obj.values():
            found.extend(_walk_for_slot_dicts(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk_for_slot_dicts(item))
    return found


def _extract_embedded_json(html: str) -> list[dict]:
    dicts: list[dict] = []
    for pattern in EMBEDDED_JSON_PATTERNS:
        m = pattern.search(html)
        if not m:
            continue
        try:
            blob = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        dicts.extend(_walk_for_slot_dicts(blob))
    return dicts


def _parse_html_fallback(html: str) -> list[dict]:
    """Best-effort scrape of a rendered slot table/list. Unverified -- see module docstring."""
    soup = BeautifulSoup(html, "html.parser")
    candidates = soup.select(
        "[class*=slot], [class*=Slot], [data-status], [class*=availab], [class*=Availab]"
    )
    dicts: list[dict] = []
    for el in candidates:
        text = " ".join(el.stripped_strings)
        if not text:
            continue
        dicts.append(
            {"_text": text, "_class": el.get("class"), "_data_status": el.get("data-status")}
        )
    return dicts


def _coerce_datetime(raw: dict) -> datetime | None:
    for key in ("start", "start_time", "starts_at", "datetime", "date_time"):
        val = raw.get(key)
        if isinstance(val, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    return datetime.strptime(val, fmt)
                except ValueError:
                    continue

    date_val = raw.get("date")
    time_val = raw.get("time") or raw.get("start_time")
    if isinstance(date_val, str) and isinstance(time_val, str):
        try:
            d = datetime.strptime(date_val, "%Y-%m-%d").date()
        except ValueError:
            return None
        m = _TIME_RE.search(time_val)
        if not m:
            return None
        return datetime.combine(d, time(int(m.group(1)), int(m.group(2))))

    text = raw.get("_text")
    if isinstance(text, str):
        m = _TIME_RE.search(text)
        if m:
            # No date in a bare text fragment -- can't build a real datetime.
            return None

    return None


def _coerce_status(raw: dict) -> str | None:
    available = raw.get("available")
    if isinstance(available, bool):
        return "free" if available else "booked"

    spaces = raw.get("spaces")
    if isinstance(spaces, int):
        return "free" if spaces > 0 else "booked"

    status_val = raw.get("status")
    if isinstance(status_val, str):
        low = status_val.strip().lower()
        if low in _STATUS_FREE_WORDS:
            return "free"
        if low in _STATUS_BOOKED_WORDS:
            return "booked"

    text = raw.get("_text")
    if isinstance(text, str):
        low = text.lower()
        if any(w in low for w in _STATUS_BOOKED_WORDS):
            return "booked"
        if any(w in low for w in _STATUS_FREE_WORDS):
            return "free"

    return None


def normalise_slot(raw: dict, *, default_venue: str = "", default_court: str = "") -> Slot | None:
    """Map a heuristically-found raw dict into a canonical Slot, or None if it can't be mapped.

    Tries a handful of common key spellings since the real payload shape is unverified --
    adjust the key lists here once scripts/probe_localtenniscourts.py has been run against
    the live site.
    """
    start = _coerce_datetime(raw)
    if start is None:
        return None

    status = _coerce_status(raw)
    if status is None:
        return None

    venue = str(raw.get("venue") or raw.get("location") or raw.get("site") or default_venue)
    court = str(raw.get("court") or raw.get("activity") or raw.get("resource") or default_court)

    return Slot(start=start, venue=venue, court=court, status=status, raw=raw)


def extract_slots(html: str) -> list[Slot]:
    """Parse slots out of a fetched page: embedded-JSON first, HTML scrape as fallback."""
    dicts = _extract_embedded_json(html)
    slots = [s for s in (normalise_slot(d) for d in dicts) if s is not None]
    if slots:
        return slots

    dicts = _parse_html_fallback(html)
    slots = [s for s in (normalise_slot(d) for d in dicts) if s is not None]
    if slots:
        return slots

    raise SlotParseError(
        "No recognisable slot data found in the fetched page. The embedded-JSON and HTML "
        "fallback heuristics in tennis_app/wednesday_watch.py are unverified against the "
        "real site. Run scripts/probe_localtenniscourts.py somewhere with real network "
        "egress, inspect the dumped payload, and adjust _extract_embedded_json / "
        "_parse_html_fallback / normalise_slot accordingly."
    )


def filter_wednesday_evening(slots: list[Slot], *, min_hour: int = MIN_HOUR) -> list[Slot]:
    return [s for s in slots if s.start.weekday() == WEDNESDAY and s.start.hour >= min_hour]


def _slot_key(s: Slot) -> str:
    return f"{s.start.isoformat()}|{s.venue}|{s.court}"


def newly_freed(prev: list[Slot], curr: list[Slot]) -> list[Slot]:
    """Return slots that were booked in `prev` and are free in `curr`.

    A slot with no prior observation is never alerted on first sighting -- there's nothing
    to compare against, so silence is correct (matches the "log quietly, alert only on
    change" behaviour the rest of this repo already follows).
    """
    prev_by_key = {_slot_key(s): s for s in prev}
    out = []
    for s in curr:
        prior = prev_by_key.get(_slot_key(s))
        if prior is not None and prior.status == "booked" and s.status == "free":
            out.append(s)
    return out


def load_cache(path: str) -> list[Slot]:
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        return []
    return [
        Slot(
            start=datetime.fromisoformat(item["start"]),
            venue=item["venue"],
            court=item["court"],
            status=item["status"],
            raw=item.get("raw", {}),
        )
        for item in raw
    ]


def save_cache(path: str, slots: list[Slot]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = [
        {
            "start": s.start.isoformat(),
            "venue": s.venue,
            "court": s.court,
            "status": s.status,
            "raw": s.raw,
        }
        for s in slots
    ]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, path)


def notify(title: str, message: str) -> None:
    """Fire a desktop/Termux notification, falling back to a printed alert."""
    if shutil.which("termux-notification"):
        subprocess.run(
            ["termux-notification", "--title", title, "--content", message],
            check=False,
        )
        return
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False)
        return
    logging.warning(
        "No desktop notifier found (termux-notification / notify-send); printing instead."
    )
    print(f"[ALERT] {title}: {message}")
