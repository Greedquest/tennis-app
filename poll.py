#!/usr/bin/env python3
"""
Simple polling script for tennis-app.
This script can be used to poll external APIs or services.
"""

import os
import sys
import requests
from datetime import datetime


def main():
    """Main polling function."""
    print(f"[{datetime.now().isoformat()}] Starting poll...")
    
    # Get environment variables (secrets passed from GitHub Actions)
    api_key = os.getenv('CLIENT_ID')
    api_url = os.getenv('CLIENT_SECRET')
    
    if not api_key:
        print("Error: CLIENT_ID environment variable not set")
        sys.exit(1)
    
    if not api_url:
        print("Error: CLIENT_SECRET environment variable not set")
        sys.exit(1)
    return   
   


if __name__ == "__main__":
    main()
