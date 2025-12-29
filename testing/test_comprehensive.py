#!/usr/bin/env python3
"""Comprehensive test for tabularise function fixes."""
import json
import os
import sys

# Add parent directory to path to import poll module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poll import tabularise


def test_empty_spaces():
    """Test that rows with empty spaces arrays are filtered out."""
    print("Test 1: Empty spaces arrays are filtered...")
    payload = {
        "rows": [
            {
                "hour": 7,
                "fromTime": "07:00",
                "day3012": {"day": "30 Dec", "total_spaces": 0, "spaces": []},
            }
        ]
    }
    result = tabularise(payload)
    # Should have 0 rows since spaces is empty
    assert result.shape[0] == 0, f"Expected 0 rows, got {result.shape[0]}"
    print("✓ Empty spaces arrays are filtered correctly")


def test_date_parsing_with_year():
    """Test that dates are parsed correctly when booking_url contains year."""
    print("\nTest 2: Date parsing with year from URL...")
    payload = {
        "rows": [
            {
                "hour": 7,
                "fromTime": "07:00",
                "day0201": {
                    "day": "02 Jan",
                    "total_spaces": 1,
                    "spaces": [
                        {
                            "venue_id": 5,
                            "name": "Test Venue",
                            "total_spaces": 1,
                            "scraped_at": "2025-12-29T19:30:16.183265",
                            "freshness": "6 mins ago",
                            "booking_url": "https://example.com/2026-01-02/slot/07:00-08:00",
                        }
                    ],
                },
            }
        ]
    }
    result = tabularise(payload)
    assert result.shape[0] == 1, f"Expected 1 row, got {result.shape[0]}"
    # Date should be parsed as 2026-01-02
    date_str = str(result.iloc[0]["Date"])
    assert date_str == "2026-01-02", f"Expected date 2026-01-02, got {date_str}"
    print(f"✓ Date parsed correctly: {date_str}")


def test_no_nan_values():
    """Test that there are no NaN values in the output."""
    print("\nTest 3: No NaN values in output...")
    sample_data_path = os.path.join(os.path.dirname(__file__), "sample_data.json")
    with open(sample_data_path) as f:
        payload = json.load(f)

    result = tabularise(payload)

    # Check for NaN values
    nan_counts = result.isna().sum()
    total_nans = nan_counts.sum()

    assert total_nans == 0, f"Found {total_nans} NaN values:\n{nan_counts[nan_counts > 0]}"
    print(f"✓ No NaN values found in {result.shape[0]} rows")


def test_venue_data_present():
    """Test that venue, venue size, and URL are present for all rows."""
    print("\nTest 4: Venue data is present for all rows...")
    sample_data_path = os.path.join(os.path.dirname(__file__), "sample_data.json")
    with open(sample_data_path) as f:
        payload = json.load(f)

    result = tabularise(payload)

    # All rows should have Venue, Venue Size, and URL
    assert result["Venue"].notna().all(), "Some rows have missing Venue"
    assert result["Venue Size"].notna().all(), "Some rows have missing Venue Size"
    assert result["URL"].notna().all(), "Some rows have missing URL"
    print(f"✓ All {result.shape[0]} rows have Venue, Venue Size, and URL")


def test_year_boundary():
    """Test that dates across year boundaries are parsed correctly."""
    print("\nTest 5: Year boundary handling...")
    payload = {
        "rows": [
            {
                "hour": 7,
                "fromTime": "07:00",
                "day3012": {
                    "day": "30 Dec",
                    "total_spaces": 1,
                    "spaces": [
                        {
                            "venue_id": 5,
                            "name": "Test Venue",
                            "total_spaces": 1,
                            "scraped_at": "2025-12-29T19:30:16.183265",
                            "freshness": "6 mins ago",
                            "booking_url": "https://example.com/2025-12-30/slot/07:00-08:00",
                        }
                    ],
                },
                "day0201": {
                    "day": "02 Jan",
                    "total_spaces": 1,
                    "spaces": [
                        {
                            "venue_id": 5,
                            "name": "Test Venue",
                            "total_spaces": 1,
                            "scraped_at": "2025-12-29T19:30:16.183265",
                            "freshness": "6 mins ago",
                            "booking_url": "https://example.com/2026-01-02/slot/07:00-08:00",
                        }
                    ],
                },
            }
        ]
    }
    result = tabularise(payload)
    assert result.shape[0] == 2, f"Expected 2 rows, got {result.shape[0]}"

    # Check both dates
    dates = sorted([str(d) for d in result["Date"]])
    assert dates[0] == "2025-12-30", f"Expected 2025-12-30, got {dates[0]}"
    assert dates[1] == "2026-01-02", f"Expected 2026-01-02, got {dates[1]}"
    print(f"✓ Year boundary handled correctly: {dates[0]} and {dates[1]}")


if __name__ == "__main__":
    print("Running comprehensive tests for tabularise function...\n")
    print("=" * 60)

    try:
        test_empty_spaces()
        test_date_parsing_with_year()
        test_no_nan_values()
        test_venue_data_present()
        test_year_boundary()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error running tests: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
