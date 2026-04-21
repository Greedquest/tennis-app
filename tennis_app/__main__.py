"""CLI entry point: ``python -m tennis_app``."""

import argparse
import json
import logging
import sys

from tennis_app.config import CACHE_STATE_PATH
from tennis_app.fetch import fetch_all_activities
from tennis_app.pipeline import run


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Tennis court availability poller")
    p.add_argument(
        "--fixtures",
        type=str,
        default=None,
        help="Path to a JSON fixture file to use instead of calling the live API. "
        "The file should contain the raw API response with a top-level 'data' array, "
        "or a plain JSON array of activity records.",
    )
    p.add_argument(
        "--cache",
        type=str,
        default=CACHE_STATE_PATH,
        help=f"Path to the cache state file (default: {CACHE_STATE_PATH})",
    )
    p.add_argument(
        "--no-notify",
        action="store_true",
        help="Disable email notifications (useful for testing).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.fixtures:
        logging.info("Loading records from fixture file: %s", args.fixtures)
        with open(args.fixtures, encoding="utf-8") as f:
            data = json.load(f)

        # Support both {"data": [...]} (raw API response) and plain [...]
        if isinstance(data, dict) and "data" in data:
            raw_records = data["data"]
        elif isinstance(data, list):
            raw_records = data
        else:
            logging.error('Fixture file must contain a JSON array or {"data": [...]}')
            return 1
    else:
        logging.info("Fetching activities from Better Admin API…")
        raw_records = fetch_all_activities()

    run(raw_records, cache_path=args.cache, notify=not args.no_notify)
    return 0


if __name__ == "__main__":
    sys.exit(main())
