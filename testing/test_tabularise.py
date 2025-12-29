#!/usr/bin/env python3
"""Test script to reproduce issues with tabularise function."""
import json
import sys
import os

# Add parent directory to path to import poll module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from poll import tabularise

# Load sample data
with open('/home/runner/work/tennis-app/tennis-app/testing/sample_data.json') as f:
    payload = json.load(f)

# Run tabularise
print("Running tabularise on sample data...\n")
result = tabularise(payload)

# Display results
print(f"Result shape: {result.shape}")
print(f"\nColumns: {result.columns.tolist()}\n")
print("Result DataFrame:")
print(result.to_string())

# Check for NaN values
print("\n\n=== NaN Analysis ===")
print(result.isna().sum())

# Display sample rows
print("\n\n=== First 10 rows ===")
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', 50)
print(result.head(10))

print("\n\n=== Data types ===")
print(result.dtypes)

print("\n\n=== Sample Date values ===")
print(result['Date'].head(20))
