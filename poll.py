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
    api_key = os.getenv('API_KEY')
    api_url = os.getenv('API_URL')
    
    if not api_key:
        print("Error: API_KEY environment variable not set")
        sys.exit(1)
    
    if not api_url:
        print("Error: API_URL environment variable not set")
        sys.exit(1)
    
    print(f"Polling endpoint: {api_url}")
    
    try:
        # Make a simple GET request with the API key
        headers = {
            'Authorization': f'Bearer {api_key}',
            'User-Agent': 'tennis-app-poller'
        }
        
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        print(f"Poll successful! Status code: {response.status_code}")
        print(f"Response length: {len(response.text)} bytes")
        
        # You can add custom logic here to process the response
        # For now, just print a summary
        print(f"[{datetime.now().isoformat()}] Poll completed successfully")
        
    except requests.exceptions.RequestException as e:
        print(f"Error polling API: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
