import marimo

__generated_with = "0.23.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import sys

    sys.path.insert(0, ".")
    import anywidget
    import json
    import traitlets

    import marimo as mo
    import pandas as pd

    from poll import fetch_all_activities, tabularise

    return anywidget, fetch_all_activities, json, mo, pd, tabularise, traitlets


@app.cell
def _(anywidget, traitlets):
    class LocalStorageCache(anywidget.AnyWidget):
        """Bidirectional localStorage bridge via anywidget.

        JS → Python (on page load): cached_json, cached_ts
        Python → JS (after fresh fetch): data_to_save triggers a write
        """

        _esm = """
        function render({ model, el }) {
            const KEY    = 'tennis_app_cache';
            const KEY_TS = 'tennis_app_cache_ts';

            // Push existing cache to Python on init
            const stored   = localStorage.getItem(KEY);
            const storedTs = localStorage.getItem(KEY_TS);
            if (stored) {
                model.set('cached_json', stored);
                model.set('cached_ts',   storedTs || '');
                model.save_changes();
            }

            // When Python sets data_to_save, persist it and echo the timestamp
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

        cached_json = traitlets.Unicode("").tag(sync=True)
        cached_ts = traitlets.Unicode("").tag(sync=True)
        data_to_save = traitlets.Unicode("").tag(sync=True)

    return (LocalStorageCache,)


@app.cell
def _(LocalStorageCache):
    cache = LocalStorageCache()
    return (cache,)


@app.cell
def _(mo):
    refresh_btn = mo.ui.button(label="🎾 Refresh Data", kind="success")
    return (refresh_btn,)


@app.cell
def _(cache, fetch_all_activities, json, pd, refresh_btn, tabularise):
    """Fetch from API on button click, otherwise restore from localStorage."""
    _EMPTY = pd.DataFrame(
        columns=["Time", "Date", "Spaces", "Venue", "Venue Size", "Age", "Scraped At", "URL"]
    )
    _df = None
    _error = None
    _is_fresh = False

    if refresh_btn.value > 0:
        try:
            _df = tabularise(fetch_all_activities())
            _is_fresh = True
        except Exception as _e:
            _error = str(_e)

    if _df is None and cache.cached_json:
        try:
            _records = json.loads(cache.cached_json)
            _df = pd.DataFrame(_records)
            if not _df.empty:
                if "Date" in _df.columns:
                    _df["Date"] = pd.to_datetime(_df["Date"], errors="coerce").dt.date
                if "Scraped At" in _df.columns:
                    _df["Scraped At"] = pd.to_datetime(_df["Scraped At"], errors="coerce")
        except Exception:
            _df = None

    current_df = _df if _df is not None else _EMPTY
    fetch_error = _error
    is_fresh = _is_fresh
    return current_df, fetch_error, is_fresh


@app.cell
def _(cache, current_df, is_fresh, json):
    """Persist fresh API data to localStorage (side-effect only, no output)."""
    if is_fresh and not current_df.empty:
        cache.data_to_save = json.dumps(
            current_df.to_dict(orient="records"), default=str
        )
    return


@app.cell
def _(cache, fetch_error, mo, refresh_btn):
    """Title, refresh button and cache status bar."""
    _ts_md = (
        mo.md(f"🕒 Last cached: **{cache.cached_ts}**")
        if cache.cached_ts
        else mo.md("_No cache — press Refresh to load_")
    )
    _status = (
        mo.callout(mo.md(f"⚠️ Fetch failed: {fetch_error}"), kind="warn")
        if fetch_error
        else _ts_md
    )
    mo.vstack(
        [
            mo.md("# 🎾 Tennis Court Availability"),
            mo.hstack([refresh_btn, _status], align="center", gap="1rem"),
        ]
    )
    return


@app.cell
def _(current_df, mo):
    """Colour-coded availability grid: venues × dates."""
    if current_df.empty:
        mo.md("_No data yet._")
    else:
        _df = current_df[current_df["Date"].notna() & current_df["Time"].notna()].copy()
        if _df.empty:
            mo.md("_No data with valid Date/Time fields._")
        else:
            _dates = sorted(_df["Date"].unique())
            _venues = sorted(_df["Venue"].dropna().unique())

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
                    _slot = _df[(_df["Venue"] == _v) & (_df["Date"] == _d)]
                    _avail = int(_slot["Spaces"].fillna(0).sum())
                    _total = len(_slot)
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
def _(current_df, mo):
    """Venue filter dropdown (always exported so the table cell can depend on it)."""
    _opts = ["All"]
    if not current_df.empty:
        _avail = current_df[current_df["Spaces"].fillna(0) > 0]
        _opts += sorted(_avail["Venue"].dropna().unique().tolist())

    venue_filter = mo.ui.dropdown(options=_opts, value="All", label="Filter by venue")

    if not current_df.empty:
        venue_filter  # display only when there is data
    return (venue_filter,)


@app.cell
def _(current_df, mo, venue_filter):
    """Detailed slots table with booking links."""
    if current_df.empty:
        mo.md("_Press **Refresh** to fetch live data._")
    else:
        _avail = current_df[current_df["Spaces"].fillna(0) > 0].copy()
        if venue_filter.value != "All":
            _avail = _avail[_avail["Venue"] == venue_filter.value]
        _avail = _avail.sort_values(["Date", "Time"]).reset_index(drop=True)

        if _avail.empty:
            mo.md("_No available slots match the current filter._")
        else:
            _rows = []
            for _, _r in _avail.iterrows():
                _spaces = int(_r["Spaces"]) if _r["Spaces"] else 0
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
                    f"<td style='padding:8px 10px'>{_r['Date'] or '—'}</td>"
                    f"<td style='padding:8px 10px'>{_r['Time'] or '—'}</td>"
                    f"<td style='padding:8px 10px;font-size:.8rem'>{_r['Venue'] or '—'}</td>"
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
