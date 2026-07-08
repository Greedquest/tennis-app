"""Tiny same-day state cache: JSON file of {"date": "...", "slots": {"HH|venue_id": spaces}}."""

import json
import os
from typing import Any


def load(path: str, today_iso: str) -> dict[str, int]:
    """Load the previous run's slot->spaces map, discarding it if it's not from today."""
    try:
        with open(path, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    if data.get("date") != today_iso:
        return {}
    return data.get("slots", {})


def save(path: str, today_iso: str, slots: dict[str, int]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"date": today_iso, "slots": slots}, f)
    os.replace(tmp, path)
