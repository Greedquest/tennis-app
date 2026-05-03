# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo>=0.23.0",
#     "polars>=1.0.0",
#     "requests>=2.28.0",
#     "anywidget>=0.9.0",
# ]
# ///

import marimo

__generated_with = "0.23.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    import logging
    import sys
    from datetime import UTC, datetime, timedelta

    import anywidget
    import marimo as mo
    import polars as pl
    import requests
    import traitlets

    # In WASM (Pyodide / molab), the `requests` library uses TCP sockets which
    # are unavailable in the browser.  pyodide-http patches requests to use the
    # browser's native fetch API instead, fixing "Failed to fetch" errors.
    if sys.platform == "emscripten":
        import pyodide_http

        pyodide_http.patch_all()

    return (
        UTC,
        anywidget,
        datetime,
        json,
        logging,
        mo,
        pl,
        requests,
        timedelta,
        traitlets,
    )


@app.cell
def _(anywidget, traitlets):
    class LocalStorageWidget(anywidget.AnyWidget):
        """Bridges browser localStorage ↔ Python.

        On page load JS pushes any stored JSON and timestamp to Python.
        When Python sets data_to_save the JS handler writes it to localStorage.
        """

        _esm = """
        function render({ model, el }) {
            const KEY    = 'tennis_app_cache';
            const KEY_TS = 'tennis_app_cache_ts';

            const stored   = localStorage.getItem(KEY);
            const storedTs = localStorage.getItem(KEY_TS);
            if (stored) {
                model.set('cached_json', stored);
                model.set('cached_ts',   storedTs || '');
                model.save_changes();
            }

            model.on('change:data_to_save', () => {
                const data = model.get('data_to_save');
                if (data) {
                    const now = new Date().toLocaleString();
                    localStorage.setItem(KEY,    data);
                    localStorage.setItem(KEY_TS, now);
                    model.set('cached_ts', now);
                    model.save_changes();
                }
            });
        }
        export default { render };
        """
        _css = ":host { display: none; }"

        cached_json = traitlets.Unicode("").tag(sync=True)
        cached_ts = traitlets.Unicode("").tag(sync=True)
        data_to_save = traitlets.Unicode("").tag(sync=True)

    return (LocalStorageWidget,)


@app.cell
def _(LocalStorageWidget, mo):
    # store is the underlying anywidget kept for Python→JS writes
    store = LocalStorageWidget()
    cache = mo.ui.anywidget(store)
    cache  # rendered so JS initialises (hidden via _css)
    return cache, store


@app.cell
def _(datetime, logging, requests, timedelta):
    _VENUES = [
        {"venue": "islington-tennis-centre", "court": "tennis-court-indoor"},
        {"venue": "islington-tennis-centre", "court": "tennis-court-outdoor"},
    ]

    def fetch_all_activities(days_ahead=5):
        today = datetime.now().date()
        dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_ahead)]
        records = []
        for vc in _VENUES:
            venue, court = vc["venue"], vc["court"]
            for date in dates:
                try:
                    r = requests.get(
                        f"https://better-admin.org.uk/api/activities/venue"
                        f"/{venue}/activity/{court}/times",
                        headers={
                            "Origin": "https://bookings.better.org.uk",
                            "User-Agent": "Mozilla/5.0 Chrome/120.0.0.0",
                            "Referer": "https://bookings.better.org.uk/",
                        },
                        params={"date": date},
                        timeout=15,
                    )
                    r.raise_for_status()
                    for act in r.json().get("data", []):
                        if isinstance(act, dict):
                            act["venue"] = venue
                            act["court"] = court
                            records.append(act)
                except Exception as e:
                    logging.warning("Failed %s/%s %s: %s", venue, court, date, e)
        return records

    return (fetch_all_activities,)


@app.cell
def _(UTC, datetime, pl):
    def tabularise(raw):
        schema = {
            "Time": pl.Utf8,
            "Date": pl.Date,
            "Spaces": pl.Int64,
            "Venue": pl.Utf8,
            "Scraped At": pl.Datetime,
            "URL": pl.Utf8,
        }
        if not raw:
            return pl.DataFrame(schema=schema)
        flat = [
            {
                "time_12h": (s := rec.get("starts_at") or {}).get("format_12_hour"),
                "time_24h": s.get("format_24_hour"),
                "end_24h": (rec.get("ends_at") or {}).get("format_24_hour"),
                "date": rec.get("date"),
                "spaces": rec.get("spaces"),
                "location": rec.get("location"),
                "timestamp": rec.get("timestamp"),
                "venue": rec.get("venue"),
                "court": rec.get("court"),
            }
            for rec in raw
        ]
        df = pl.DataFrame(flat)
        return df.select(
            pl.col("time_12h").alias("Time"),
            pl.col("date").str.strptime(pl.Date, "%Y-%m-%d", strict=False).alias("Date"),
            pl.col("spaces").cast(pl.Int64).alias("Spaces"),
            pl.col("location").alias("Venue"),
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
    refresh_btn = mo.ui.button(label="🔄 Refresh", kind="success")
    return (refresh_btn,)


@app.cell
def _(fetch_all_activities, refresh_btn, tabularise):
    """Fetch fresh data when the button is clicked."""
    fresh_df = None
    fetch_error = None
    if refresh_btn.value:
        try:
            fresh_df = tabularise(fetch_all_activities())
        except Exception as err:
            fetch_error = str(err)
    return fetch_error, fresh_df


@app.cell
def _(cache, json, pl):
    """Parse the localStorage cache into a DataFrame."""
    cached_df = None
    cache_error = None
    raw_json = cache.value.get("cached_json", "")
    if raw_json:
        try:
            rows = json.loads(raw_json)
            if rows:
                cached_df = pl.from_dicts(rows, schema_overrides={"Spaces": pl.Int64})
                if "Date" in cached_df.columns:
                    cached_df = cached_df.with_columns(
                        pl.col("Date").cast(pl.Utf8).str.to_date(strict=False)
                    )
                if "Scraped At" in cached_df.columns:
                    cached_df = cached_df.with_columns(
                        pl.col("Scraped At").cast(pl.Utf8).str.to_datetime(strict=False)
                    )
        except Exception as err:
            cache_error = f"Cache unreadable ({err}) — press Refresh to reload."
    return cache_error, cached_df


@app.cell
def _(cached_df, fresh_df, pl):
    """Compute row-level diff: new slots, gone slots, changed availability."""
    diff_df = None
    if fresh_df is not None and cached_df is not None:
        keys = ["Date", "Time", "Venue"]

        added = (
            fresh_df.select(keys + ["Spaces"])
            .join(cached_df.select(keys), on=keys, how="anti")
            .with_columns(
                pl.lit("🟢 new").alias("Change"),
                pl.lit(None).cast(pl.Int64).alias("Prev Spaces"),
            )
        )
        removed = (
            cached_df.select(keys + ["Spaces"])
            .join(fresh_df.select(keys), on=keys, how="anti")
            .with_columns(
                pl.lit("🔴 gone").alias("Change"),
                pl.lit(None).cast(pl.Int64).alias("Prev Spaces"),
            )
        )
        changed = (
            fresh_df.select(keys + ["Spaces"])
            .join(cached_df.select(keys + ["Spaces"]), on=keys, suffix="_prev")
            .filter(pl.col("Spaces") != pl.col("Spaces_prev"))
            .rename({"Spaces_prev": "Prev Spaces"})
            .with_columns(pl.lit("🟡 changed").alias("Change"))
        )
        diff_df = pl.concat(
            [
                added.select(keys + ["Spaces", "Prev Spaces", "Change"]),
                removed.select(keys + ["Spaces", "Prev Spaces", "Change"]),
                changed.select(keys + ["Spaces", "Prev Spaces", "Change"]),
            ],
            how="diagonal",
        ).sort(["Date", "Time", "Venue"])
    return (diff_df,)


@app.cell
def _(fresh_df, json, refresh_btn, store):
    """Persist fresh data to localStorage after a successful fetch (side-effect)."""
    if refresh_btn.value and fresh_df is not None and not fresh_df.is_empty():
        store.data_to_save = json.dumps(fresh_df.to_dicts(), default=str)
    return


@app.cell
def _(cache, cache_error, fetch_error, mo, refresh_btn):
    """Header, refresh button, and status line."""
    cached_ts = cache.value.get("cached_ts", "")
    status_md = (
        mo.callout(mo.md(f"⚠️ Fetch error: {fetch_error}"), kind="warn")
        if fetch_error
        else mo.callout(mo.md(f"⚠️ {cache_error}"), kind="warn")
        if cache_error
        else mo.md(f"🕒 Cached: **{cached_ts}**")
        if cached_ts
        else mo.md("_No cache yet — press Refresh_")
    )
    mo.vstack(
        [
            mo.md("# 🎾 Tennis Court Availability"),
            mo.hstack([refresh_btn, status_md], align="center"),
        ]
    )
    return


@app.cell
def _(cached_df, diff_df, fresh_df, mo, pl):
    """Summary stats row."""
    display_df = fresh_df if fresh_df is not None else cached_df
    n_slots = display_df.height if display_df is not None else 0
    n_avail = (
        display_df.filter(pl.col("Spaces").fill_null(0) > 0).height if display_df is not None else 0
    )
    n_venues = display_df["Venue"].drop_nulls().n_unique() if display_df is not None else 0
    n_changes = diff_df.height if diff_df is not None else 0

    mo.hstack(
        [
            mo.stat(value=str(n_slots), label="Total slots", caption="fresh or cached"),
            mo.stat(value=str(n_avail), label="Available", caption="spaces > 0"),
            mo.stat(value=str(n_venues), label="Venues", caption="unique"),
            mo.stat(value=str(n_changes), label="Changes", caption="vs cached"),
        ],
        justify="start",
    )
    return


@app.cell
def _(cached_df, diff_df, fresh_df, mo):
    """Tabs: Cache · Fresh · Diff."""

    def _slot_table(df, label):
        if df is None or df.is_empty():
            return mo.md(f"_No {label}_")
        return mo.ui.table(
            df,
            format_mapping={"URL": lambda u: f'<a href="{u}" target="_blank">Book →</a>'},
            show_column_summaries=False,
        )

    def _diff_table(df):
        if df is None or df.is_empty():
            return mo.md("_No differences detected_")
        return mo.ui.table(df, show_column_summaries=False)

    mo.ui.tabs(
        {
            f"📦 Cache ({cached_df.height if cached_df is not None else 0})": _slot_table(
                cached_df, "cached data"
            ),
            f"🆕 Fresh ({fresh_df.height if fresh_df is not None else 0})": _slot_table(
                fresh_df, "fresh data — press Refresh"
            ),
            f"🔀 Diff ({diff_df.height if diff_df is not None else 0})": _diff_table(diff_df),
        }
    )
    return


if __name__ == "__main__":
    app.run()
