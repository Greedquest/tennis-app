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
    import sys

    import anywidget
    import marimo as mo
    import polars as pl
    import traitlets

    # In WASM (Pyodide / molab), requests uses TCP sockets which don't exist in
    # the browser.  pyodide-http patches requests to use the browser's native
    # fetch API — this must run before tennis_app is imported.
    if sys.platform == "emscripten":
        import pyodide_http

        pyodide_http.patch_all()

    return anywidget, json, mo, pl, sys, traitlets


@app.cell
def _(sys):
    """Import business logic from tennis_app; provide stubs when unavailable (WASM)."""
    is_wasm = sys.platform == "emscripten"

    try:
        from tennis_app.cache import load_prev_rows
        from tennis_app.config import CACHE_STATE_PATH
        from tennis_app.fetch import fetch_all_activities
        from tennis_app.transform import tabularise
    except ImportError:
        # tennis_app is a local package unavailable in WASM (molab).
        # Cached data from localStorage is still displayed; Refresh is disabled.
        import polars as _pl

        CACHE_STATE_PATH = "cache/state.json"

        def fetch_all_activities(**kwargs):  # noqa: ARG001
            raise RuntimeError(
                "Refresh requires local execution — "
                "tennis_app is not available in WASM (molab). "
                "Run `marimo run dashboard.py` from the repository root."
            )

        def tabularise(raw):  # noqa: ARG001
            return _pl.DataFrame()

        def load_prev_rows(path):  # noqa: ARG001
            return _pl.DataFrame()

    return CACHE_STATE_PATH, fetch_all_activities, is_wasm, load_prev_rows, tabularise


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
def _(mo):
    refresh_btn = mo.ui.run_button(label="🔄 Refresh", kind="success")
    return (refresh_btn,)


@app.cell
def _(fetch_all_activities, refresh_btn, tabularise):
    """Fetch fresh data from the API when the button is clicked."""
    fresh_df = None
    fetch_error = None
    if refresh_btn.value:
        try:
            fresh_df = tabularise(fetch_all_activities())
        except Exception as err:
            fetch_error = str(err)
    return fetch_error, fresh_df


@app.cell
def _(CACHE_STATE_PATH, cache, is_wasm, json, load_prev_rows, pl):
    """Load previously-saved state: action cache file (local) or localStorage (WASM)."""
    cached_df = None
    cache_error = None

    if is_wasm:
        # WASM (molab): read from browser localStorage (set by a previous Refresh)
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
    else:
        # Local: read the JSON state file written by the GitHub Actions poller
        try:
            loaded = load_prev_rows(CACHE_STATE_PATH)
            cached_df = loaded if not loaded.is_empty() else None
        except Exception as err:
            cache_error = f"Could not read {CACHE_STATE_PATH}: {err}"

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
def _(fresh_df, is_wasm, json, refresh_btn, store):
    """Persist fresh data to localStorage after a successful fetch (WASM only)."""
    if is_wasm and refresh_btn.value and fresh_df is not None and not fresh_df.is_empty():
        store.data_to_save = json.dumps(fresh_df.to_dicts(), default=str)
    return


@app.cell
def _(CACHE_STATE_PATH, cache, cache_error, cached_df, fetch_error, fresh_df, is_wasm, mo, refresh_btn):
    """Header, refresh button, and status line."""
    if fetch_error:
        _status = mo.callout(mo.md(f"⚠️ Fetch error: {fetch_error}"), kind="warn")
    elif fresh_df is not None:
        _status = mo.callout(mo.md(f"✅ Refreshed — **{fresh_df.height}** slots loaded"), kind="success")
    elif cache_error:
        _status = mo.callout(mo.md(f"⚠️ {cache_error}"), kind="warn")
    elif is_wasm:
        _ts = cache.value.get("cached_ts", "")
        _status = mo.md(f"🕒 Cached: **{_ts}**") if _ts else mo.md("_No cache yet — press Refresh_")
    elif cached_df is not None:
        _status = mo.md(f"📁 Cache loaded from `{CACHE_STATE_PATH}`")
    else:
        _status = mo.md(f"_No cache at `{CACHE_STATE_PATH}` — run the poller first_")
    mo.vstack(
        [
            mo.md("# 🎾 Tennis Court Availability"),
            mo.hstack([refresh_btn, _status], align="center"),
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
