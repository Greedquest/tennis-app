# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo>=0.23.0",
#     "polars>=1.0.0",
#     "requests>=2.28.0",
# ]
# ///

import marimo

__generated_with = "0.23.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import logging
    from datetime import UTC, datetime, timedelta

    import marimo as mo
    import polars as pl
    import requests

    return UTC, datetime, logging, mo, pl, requests, timedelta


@app.cell
def _(datetime, logging, requests, timedelta):
    _VENUES = [
        {"venue": "islington-tennis-centre", "court": "tennis-court-indoor"},
        {"venue": "islington-tennis-centre", "court": "tennis-court-outdoor"},
    ]

    def fetch_all_activities(days_ahead=5):
        today = datetime.now().date()
        dates = [
            (today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_ahead)
        ]
        all_records = []
        for vc in _VENUES:
            venue, court = vc["venue"], vc["court"]
            for date in dates:
                try:
                    url = (
                        f"https://better-admin.org.uk/api/activities/venue/"
                        f"{venue}/activity/{court}/times"
                    )
                    r = requests.get(
                        url,
                        headers={
                            "Origin": "https://bookings.better.org.uk",
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/120.0.0.0 Safari/537.36"
                            ),
                            "Accept": "application/json, text/plain, */*",
                            "Referer": "https://bookings.better.org.uk/",
                        },
                        params={"date": date},
                        timeout=15,
                    )
                    r.raise_for_status()
                    for activity in r.json().get("data", []):
                        if isinstance(activity, dict):
                            activity["venue"] = venue
                            activity["court"] = court
                            all_records.append(activity)
                except Exception as e:
                    logging.warning("Failed %s/%s %s: %s", venue, court, date, e)
        return all_records

    return (fetch_all_activities,)


@app.cell
def _(UTC, datetime, pl):
    def tabularise(raw_records):
        empty = pl.DataFrame(
            schema={
                "Time": pl.Utf8,
                "Date": pl.Date,
                "Spaces": pl.Int64,
                "Venue": pl.Utf8,
                "Venue Size": pl.Utf8,
                "Age": pl.Utf8,
                "Scraped At": pl.Datetime,
                "URL": pl.Utf8,
            }
        )
        if not raw_records:
            return empty
        flat = []
        for rec in raw_records:
            starts_at = rec.get("starts_at") or {}
            ends_at = rec.get("ends_at") or {}
            flat.append(
                {
                    "time_12h": starts_at.get("format_12_hour"),
                    "time_24h": starts_at.get("format_24_hour"),
                    "end_24h": ends_at.get("format_24_hour"),
                    "date": rec.get("date"),
                    "spaces": rec.get("spaces"),
                    "location": rec.get("location"),
                    "timestamp": rec.get("timestamp"),
                    "venue": rec.get("venue"),
                    "court": rec.get("court"),
                }
            )
        df = pl.DataFrame(flat)
        return df.select(
            pl.col("time_12h").alias("Time"),
            pl.col("date").str.strptime(pl.Date, "%Y-%m-%d", strict=False).alias("Date"),
            pl.col("spaces").cast(pl.Int64).alias("Spaces"),
            pl.col("location").alias("Venue"),
            pl.lit(None).cast(pl.Utf8).alias("Venue Size"),
            pl.lit(None).cast(pl.Utf8).alias("Age"),
            pl.col("timestamp")
            .cast(pl.Int64)
            .map_elements(
                lambda ts: datetime.fromtimestamp(ts, tz=UTC) if ts is not None else None,
                return_dtype=pl.Datetime("us", "UTC"),
            )
            .cast(pl.Datetime("us"))
            .alias("Scraped At"),
            (
                pl.lit("https://bookings.better.org.uk/location/")
                + pl.col("venue")
                + pl.lit("/")
                + pl.col("court")
                + pl.lit("/")
                + pl.col("date")
                + pl.lit("/by-time/slot/")
                + pl.col("time_24h")
                + pl.lit("-")
                + pl.col("end_24h")
            ).alias("URL"),
        )

    return (tabularise,)


@app.cell
def _(mo):
    refresh_btn = mo.ui.button(label="🎾 Refresh Data", kind="success")
    return (refresh_btn,)


@app.cell
def _(fetch_all_activities, pl, refresh_btn, tabularise):
    """Fetch from API on button click."""
    _SCHEMA = {
        "Time": pl.Utf8,
        "Date": pl.Date,
        "Spaces": pl.Int64,
        "Venue": pl.Utf8,
        "Venue Size": pl.Utf8,
        "Age": pl.Utf8,
        "Scraped At": pl.Datetime,
        "URL": pl.Utf8,
    }
    _EMPTY = pl.DataFrame(schema=_SCHEMA)

    _df = None
    _error = None

    if refresh_btn.value > 0:
        try:
            _df = tabularise(fetch_all_activities())
        except Exception as _e:
            _error = str(_e)

    current_df = _df if _df is not None else _EMPTY
    fetch_error = _error
    return current_df, fetch_error


@app.cell
def _(fetch_error, mo, refresh_btn):
    """Title, refresh button and status bar."""
    _status = (
        mo.callout(mo.md(f"⚠️ Fetch failed: {fetch_error}"), kind="warn")
        if fetch_error
        else mo.md("_Press Refresh to fetch live data_")
    )
    mo.vstack(
        [
            mo.md("# 🎾 Tennis Court Availability"),
            mo.hstack([refresh_btn, _status], align="center", gap="1rem"),
        ]
    )
    return


@app.cell
def _(current_df, mo, pl):
    """Colour-coded availability grid: venues x dates."""
    if current_df.is_empty():
        mo.md("_No data yet._")
    else:
        _df = current_df.filter(
            pl.col("Date").is_not_null() & pl.col("Time").is_not_null()
        )
        if _df.is_empty():
            mo.md("_No data with valid Date/Time fields._")
        else:
            _dates = sorted(_df["Date"].unique().to_list())
            _venues = sorted(_df["Venue"].drop_nulls().unique().to_list())

            _th = "".join(
                f"<th style='padding:6px 10px;background:#1a1a2e;color:#eee;"
                f"font-size:.75rem;white-space:nowrap'>{d}</th>"
                for d in _dates
            )
            _header_row = (
                f"<tr><th style='padding:6px 10px;background:#1a1a2e;color:#eee'></th>{_th}</tr>"
            )

            _body_rows = []
            for _v in _venues:
                _cells = [
                    f"<td style='padding:6px 8px;font-weight:600;background:#f5f5f5;"
                    f"white-space:nowrap;font-size:.85rem'>{_v}</td>"
                ]
                for _d in _dates:
                    _slot = _df.filter(
                        (pl.col("Venue") == _v) & (pl.col("Date") == _d)
                    )
                    _avail = int(_slot["Spaces"].fill_null(0).sum())
                    _total = _slot.height
                    if _total == 0:
                        _bg, _fg, _lbl = "#e0e0e0", "#888", "—"
                    elif _avail == 0:
                        _bg, _fg, _lbl = "#ffcdd2", "#c62828", "Full"
                    elif _avail <= 2:
                        _bg, _fg, _lbl = "#fff9c4", "#f57f17", f"{_avail} left"
                    else:
                        _bg, _fg, _lbl = "#c8e6c9", "#2e7d32", f"{_avail} free"
                    _cells.append(
                        f"<td style='padding:6px 8px;background:{_bg};color:{_fg};"
                        f"text-align:center;font-size:.8rem;font-weight:600'>{_lbl}</td>"
                    )
                _body_rows.append(f"<tr>{''.join(_cells)}</tr>")

            mo.Html(
                "<div style='overflow-x:auto'>"
                "<table style='border-collapse:collapse;width:100%;font-family:sans-serif'>"
                f"<thead>{_header_row}</thead>"
                f"<tbody>{''.join(_body_rows)}</tbody>"
                "</table></div>"
            )
    return


@app.cell
def _(current_df, mo, pl):
    """Venue filter dropdown (always exported so the table cell can depend on it)."""
    _opts = ["All"]
    if not current_df.is_empty():
        _avail = current_df.filter(pl.col("Spaces").fill_null(0) > 0)
        _opts += sorted(_avail["Venue"].drop_nulls().unique().to_list())

    venue_filter = mo.ui.dropdown(options=_opts, value="All", label="Filter by venue")

    if not current_df.is_empty():
        venue_filter  # display only when there is data
    return (venue_filter,)


@app.cell
def _(current_df, mo, pl, venue_filter):
    """Detailed slots table with booking links."""
    if current_df.is_empty():
        mo.md("_Press **Refresh** to fetch live data._")
    else:
        _avail = current_df.filter(pl.col("Spaces").fill_null(0) > 0)
        if venue_filter.value != "All":
            _avail = _avail.filter(pl.col("Venue") == venue_filter.value)
        _avail = _avail.sort(["Date", "Time"])

        if _avail.is_empty():
            mo.md("_No available slots match the current filter._")
        else:
            _rows = []
            for _r in _avail.to_dicts():
                _spaces = _r.get("Spaces") or 0
                _sbg = "#c8e6c9" if _spaces > 2 else "#fff9c4"
                _url = _r.get("URL")
                _book = (
                    f'<a href="{_url}" target="_blank" '
                    f'style="color:#1565c0;font-weight:600;text-decoration:none">Book →</a>'
                    if _url
                    else "—"
                )
                _rows.append(
                    "<tr>"
                    f"<td style='padding:8px 10px'>{_r.get('Date') or '—'}</td>"
                    f"<td style='padding:8px 10px'>{_r.get('Time') or '—'}</td>"
                    f"<td style='padding:8px 10px;font-size:.8rem'>{_r.get('Venue') or '—'}</td>"
                    f"<td style='padding:8px 10px;text-align:center;"
                    f"background:{_sbg};font-weight:600'>{_spaces}</td>"
                    f"<td style='padding:8px 10px;text-align:center'>{_book}</td>"
                    "</tr>"
                )

            _thead = (
                "<tr style='background:#1a1a2e;color:#eee'>"
                "<th style='padding:8px 10px;text-align:left'>Date</th>"
                "<th style='padding:8px 10px;text-align:left'>Time</th>"
                "<th style='padding:8px 10px;text-align:left'>Venue</th>"
                "<th style='padding:8px 10px;text-align:center'>Spaces</th>"
                "<th style='padding:8px 10px;text-align:center'>Book</th>"
                "</tr>"
            )
            mo.Html(
                "<div style='overflow-x:auto'>"
                "<table style='border-collapse:collapse;width:100%;font-family:sans-serif'>"
                f"<thead>{_thead}</thead>"
                f"<tbody>{''.join(_rows)}</tbody>"
                "</table></div>"
            )
    return
