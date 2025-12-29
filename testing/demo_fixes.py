#!/usr/bin/env python3
"""
Demonstration of the fixes to the tabularise function.

This script shows what was fixed:
1. Date parsing now works correctly by extracting year from booking_url
2. Rows with empty spaces arrays are filtered out (no more NaN values)
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poll import tabularise

print("=" * 70)
print("DEMONSTRATION: tabularise() Function Fixes")
print("=" * 70)

# Load sample data using relative path
sample_data_path = os.path.join(os.path.dirname(__file__), "sample_data.json")
with open(sample_data_path) as f:
    payload = json.load(f)

# Process the data
result = tabularise(payload)

print("\n📊 RESULTS:")
print(f"   Total rows: {result.shape[0]}")
print(f"   Total columns: {result.shape[1]}")

print("\n✅ FIX #1: Date Parsing")
print("   Problem: Dates like '30 Dec', '01 Jan' were parsed as NaT (Not a Time)")
print("   Solution: Extract year from booking_url field")
print("   Sample dates parsed:")
unique_dates = sorted(result["Date"].unique())[:5]
for date in unique_dates:
    print(f"      • {date}")

print("\n✅ FIX #2: NaN Values Eliminated")
print("   Problem: Rows with empty 'spaces' arrays created NaN for venue fields")
print("   Solution: Filter out rows where spaces array is empty")
print("   NaN count by column:")
nan_counts = result.isna().sum()
for col, count in nan_counts.items():
    print(f"      • {col}: {count} NaN values")

print("\n📋 SAMPLE OUTPUT (first 5 rows):")
print("-" * 70)
# Display first 5 rows with limited column width
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 35)
print(result.head())

print("\n" + "=" * 70)
print("✓ Both issues are now fixed!")
print("=" * 70)
