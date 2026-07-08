"""Parse court availability out of localtenniscourts.com's server-rendered HTML.

The page has no JSON API (``/api/availability`` explicitly rejects non-HTML
requests with ``{"error": "Only HTML requests are supported here"}``). The
data instead ships embedded in the initial HTML as a hydration blob (a
``self.$R`` reference-table literal used by the site's SSR streaming setup),
structured roughly as::

    hour:19,fromTime:"19:00",day0807:$R[n]={day:"08 Jul",total_spaces:0,
        spaces:$R[m]=[{venue_id:1,name:"Highbury Fields",total_spaces:0,
        scraped_at:"...",freshness:"...",booking_url:"..."}]}, day0907:...

This isn't valid JSON (unquoted keys, ``$R[n]=`` back-references, JS literal
syntax), so it's picked apart with targeted regexes rather than parsed as a
document tree. The day columns run left-to-right starting from today, so the
first ``dayMMDD`` block within each hour row is always today's.
"""

import re
from dataclasses import dataclass

import requests

PAGE_URL = "https://localtenniscourts.com/"
DEFAULT_QUERY = "highbury-fields,islington-tennis-centre-outdoor"

_HOUR_RE = re.compile(r'hour:(\d+),fromTime:"(\d{2}:\d{2})"')
_DAY_RE = re.compile(
    r'day\d{4}:\$R\[\d+\]=\{day:"[^"]*",total_spaces:(\d+),spaces:\$R\[\d+\]=\[(.*?)\]\}'
)
_VENUE_RE = re.compile(
    r'\{venue_id:(\d+),name:"([^"]+)",total_spaces:(\d+),'
    r'scraped_at:"[^"]*",freshness:"[^"]*",booking_url:"([^"]+)"\}'
)
_GRID_END_RE = re.compile(r"venues:\$R\[\d+\]=\[")


@dataclass
class VenueSlot:
    venue_id: int
    name: str
    spaces: int
    booking_url: str


@dataclass
class HourSlot:
    hour: int
    from_time: str
    total_spaces: int
    venues: list[VenueSlot]


def fetch_page(query: str = DEFAULT_QUERY, *, timeout: float = 15) -> str:
    """Fetch the rendered page for the given venue query string."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html",
    }
    r = requests.get(PAGE_URL, params={"q": query}, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def parse_today_slots(html: str) -> list[HourSlot]:
    """
    Extract today's hourly availability from the page's embedded data blob.

    Returns one HourSlot per hour row present on the page (today's column
    only), each carrying whichever venues had an entry for that hour.
    """
    grid_end = _GRID_END_RE.search(html)
    end = grid_end.start() if grid_end else len(html)

    anchors = list(_HOUR_RE.finditer(html, 0, end))
    slots: list[HourSlot] = []

    for i, m in enumerate(anchors):
        hour = int(m.group(1))
        from_time = m.group(2)
        block_end = anchors[i + 1].start() if i + 1 < len(anchors) else end
        block = html[m.end() : block_end]

        days = _DAY_RE.findall(block)
        if not days:
            continue

        today_total, today_spaces_blob = days[0]
        venues = [
            VenueSlot(venue_id=int(vid), name=name, spaces=int(spaces), booking_url=url)
            for vid, name, spaces, url in _VENUE_RE.findall(today_spaces_blob)
        ]
        slots.append(
            HourSlot(hour=hour, from_time=from_time, total_spaces=int(today_total), venues=venues)
        )

    return slots
