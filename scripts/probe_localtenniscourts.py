#!/usr/bin/env python3
"""THROWAWAY probe: dump full HTML of localtenniscourts.com for a local fixture.

Not part of the app. Confirmed SSR + table structure already. This final
pass just dumps the complete raw HTML between markers so it can be saved
as a local test fixture. Delete after use.
"""

import requests

URL = "https://localtenniscourts.com/?q=highbury-fields%2Cislington-tennis-centre-outdoor"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def main() -> int:
    r = requests.get(URL, headers={"User-Agent": UA}, timeout=20)
    print(f"status={r.status_code} len={len(r.text)}")
    print("===FIXTURE_START===")
    print(r.text)
    print("===FIXTURE_END===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
