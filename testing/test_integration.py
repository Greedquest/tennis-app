#!/usr/bin/env python3
"""Integration test simulating the full workflow."""

import json
import os
import sys
import tempfile

# Add parent directory to path to import poll module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poll import diff_tables, key_of, load_prev_rows, save_rows, tabularise


def test_full_workflow():
    """Test the full workflow with tabularise, save, load, and diff."""
    print("Integration Test: Full workflow simulation")
    print("=" * 60)

    # Load sample data using relative path
    sample_data_path = os.path.join(os.path.dirname(__file__), "sample_data.json")
    with open(sample_data_path) as f:
        payload = json.load(f)

    # Step 1: Tabularise the data
    print("\n1. Tabularising data...")
    df = tabularise(payload)
    print(f"   ✓ Created DataFrame with {df.shape[0]} rows and {df.shape[1]} columns")

    # Step 2: Check for data quality
    print("\n2. Checking data quality...")

    # No NaN values
    nan_count = df.isna().sum().sum()
    assert nan_count == 0, f"Found {nan_count} NaN values"
    print("   ✓ No NaN values found")

    # All required columns present
    required_columns = ["Time", "Date", "Spaces", "Venue", "Venue Size", "Age", "Scraped At", "URL"]
    for col in required_columns:
        assert col in df.columns, f"Missing column: {col}"
    print(f"   ✓ All required columns present: {', '.join(required_columns)}")

    # Dates are properly parsed
    assert df["Date"].dtype == "object" or df["Date"].dtype.name.startswith("datetime"), (
        f"Date column has unexpected type: {df['Date'].dtype}"
    )
    # Check that dates are not NaT
    date_sample = str(df.iloc[0]["Date"])
    assert "NaT" not in date_sample, f"Dates not parsed correctly: {date_sample}"
    print(f"   ✓ Dates parsed correctly (sample: {date_sample})")

    # Step 3: Save and load
    print("\n3. Testing save and load...")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "test_cache.json")
        save_rows(cache_path, df)
        print(f"   ✓ Saved to {cache_path}")

        loaded_df = load_prev_rows(cache_path)
        print(f"   ✓ Loaded {loaded_df.shape[0]} rows")

        # Verify loaded data matches
        assert loaded_df.shape == df.shape, f"Shape mismatch: {loaded_df.shape} vs {df.shape}"
        print("   ✓ Loaded data matches saved data")

    # Step 4: Test diff functionality
    print("\n4. Testing diff functionality...")
    changed_keys = diff_tables(df, df)
    assert len(changed_keys) == 0, f"Expected no changes, got {len(changed_keys)}"
    print("   ✓ Diff works correctly (no changes detected for identical data)")

    # Step 5: Test key generation
    print("\n5. Testing key generation...")
    for _, row in df.head().iterrows():
        key = key_of(row)
        assert "|" in key, f"Invalid key format: {key}"
        # Key should contain date, time, and venue
        assert str(row["Date"]) in key, f"Date not in key: {key}"
        assert str(row["Venue"]) in key, f"Venue not in key: {key}"
    print("   ✓ Key generation works correctly")

    print("\n" + "=" * 60)
    print("✓ Integration test passed!")
    return True


if __name__ == "__main__":
    try:
        test_full_workflow()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
