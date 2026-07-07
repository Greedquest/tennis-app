"""Tests for the target-slot filter and booked->free alert logic."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import polars as pl

from tennis_app.pipeline import run, within_poll_window
from tennis_app.transform import filter_target_records, newly_free, tabularise

WED = date(2026, 7, 8)  # a Wednesday
TUE = date(2026, 7, 7)  # a Tuesday
LON = ZoneInfo("Europe/London")


def _rec(date_str: str, hh: str, spaces: int, court: str = "tennis-court-outdoor") -> dict:
    """Minimal raw API record shaped like fetch_all_activities() output."""
    return {
        "starts_at": {"format_12_hour": f"{hh}", "format_24_hour": hh},
        "ends_at": {"format_24_hour": hh},
        "date": date_str,
        "spaces": spaces,
        "location": "Highbury Fields" if "highbury" in court else "Islington",
        "timestamp": 1_768_287_600,
        "venue": "islington-tennis-centre",
        "court": court,
    }


# --------------------------------------------------------------------------- #
# filter_target_records
# --------------------------------------------------------------------------- #
def test_filter_keeps_only_wed_evening_on_date():
    records = [
        _rec("2026-07-08", "19:00", 1),  # keep: Wed, 19:00
        _rec("2026-07-08", "20:00", 0),  # keep: Wed, 20:00
        _rec("2026-07-08", "18:00", 1),  # drop: before 19:00
        _rec("2026-07-07", "20:00", 1),  # drop: Tuesday
        _rec("2026-07-15", "20:00", 1),  # drop: different Wednesday
    ]
    kept = filter_target_records(records, weekday=2, min_hour=19, on_date=WED)
    times = sorted(r["starts_at"]["format_24_hour"] for r in kept)
    assert times == ["19:00", "20:00"]


def test_filter_without_on_date_allows_any_wednesday():
    records = [_rec("2026-07-08", "19:00", 1), _rec("2026-07-15", "19:00", 1)]
    kept = filter_target_records(records, weekday=2, min_hour=19, on_date=None)
    assert len(kept) == 2


def test_filter_handles_malformed_records():
    records = [{"date": "not-a-date"}, {"date": "2026-07-08"}, {}]
    assert filter_target_records(records, weekday=2, min_hour=19, on_date=WED) == []


# --------------------------------------------------------------------------- #
# newly_free
# --------------------------------------------------------------------------- #
def test_newly_free_detects_booked_to_free():
    prev = tabularise([_rec("2026-07-08", "19:00", 0)])  # was booked
    curr = tabularise([_rec("2026-07-08", "19:00", 2)])  # now free
    out = newly_free(curr, prev)
    assert out.height == 1


def test_newly_free_ignores_still_free_and_free_to_booked():
    prev = tabularise([_rec("2026-07-08", "19:00", 2), _rec("2026-07-08", "20:00", 2)])
    curr = tabularise([_rec("2026-07-08", "19:00", 1), _rec("2026-07-08", "20:00", 0)])
    assert newly_free(curr, prev).is_empty()


def test_newly_free_ignores_brand_new_slots():
    prev = tabularise([])  # first run: nothing known
    curr = tabularise([_rec("2026-07-08", "19:00", 2)])
    assert newly_free(curr, prev).is_empty()


def test_two_venues_same_time_do_not_collide():
    # Highbury and Islington outdoor both report location "Multiple"; the two
    # 19:00 slots must be tracked as distinct (keyed by their booking URL).
    hf = _rec("2026-07-08", "19:00", 0, court="highbury-fields-tennis")
    itc = _rec("2026-07-08", "19:00", 0, court="tennis-court-outdoor")
    hf["location"] = itc["location"] = "Multiple"
    prev = tabularise([hf, itc])  # both booked

    hf_free = _rec("2026-07-08", "19:00", 1, court="highbury-fields-tennis")
    itc_free = _rec("2026-07-08", "19:00", 0, court="tennis-court-outdoor")
    hf_free["location"] = itc_free["location"] = "Multiple"
    curr = tabularise([hf_free, itc_free])  # only Highbury opened up

    out = newly_free(curr, prev)
    assert out.height == 1
    assert "highbury-fields-tennis" in out["URL"][0]


# --------------------------------------------------------------------------- #
# within_poll_window
# --------------------------------------------------------------------------- #
def test_window_true_on_wed_afternoon():
    assert within_poll_window(datetime(2026, 7, 8, 14, 30, tzinfo=LON))


def test_window_false_off_hours_and_off_day():
    assert not within_poll_window(datetime(2026, 7, 8, 9, 0, tzinfo=LON))  # too early
    assert not within_poll_window(datetime(2026, 7, 8, 22, 0, tzinfo=LON))  # 22:00 exclusive
    assert not within_poll_window(datetime(2026, 7, 7, 14, 0, tzinfo=LON))  # Tuesday


# --------------------------------------------------------------------------- #
# run() end-to-end (notify disabled)
# --------------------------------------------------------------------------- #
def test_run_alerts_only_on_transition(tmp_path):
    cache = str(tmp_path / "state.json")
    at = datetime(2026, 7, 8, 13, 0, tzinfo=LON)

    # First poll: slot booked. No prior state -> caches, no alert.
    df1 = run([_rec("2026-07-08", "19:00", 0)], cache, notify=False, now=at)
    assert df1.height == 1
    assert int(df1["Spaces"][0]) == 0

    # Second poll: same slot now free -> this is the opening we care about.
    df2 = run([_rec("2026-07-08", "19:00", 2)], cache, notify=False, now=at)
    prev = tabularise([_rec("2026-07-08", "19:00", 0)])
    assert newly_free(df2, prev).height == 1


def test_run_skips_outside_window():
    off = datetime(2026, 7, 7, 14, 0, tzinfo=LON)  # Tuesday
    out = run([_rec("2026-07-08", "19:00", 2)], "unused.json", notify=False, now=off)
    assert isinstance(out, pl.DataFrame)
    assert out.is_empty()
