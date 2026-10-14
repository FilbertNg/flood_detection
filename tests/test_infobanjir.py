from datetime import date, datetime
from pathlib import Path

from floodready import infobanjir as ib

FIX = Path(__file__).parent / "fixtures"


def read(name):
    return (FIX / name).read_text(encoding="utf-8", errors="ignore")


# ---------- value parsing ----------

def test_to_float_treats_sensor_fault_and_blanks_as_missing():
    assert ib.to_float("3.21") == 3.21
    assert ib.to_float(" 0.0 ") == 0.0
    for bad in ["-9999", -9999, "", "-", "N/A", None]:
        assert ib.to_float(bad) is None


# ---------- live water-level table ----------

def test_parse_wl_live_reads_sg_binjai_with_thresholds():
    rows = ib.parse_wl_live(read("infobanjir_wl_live_SEL.html"), state="SEL")
    binjai = next(r for r in rows if r["graph_id"] == "PEKANMERU")
    assert binjai["station_code"] == "3112401"
    assert binjai["station_name"] == "Sg. Binjai di Pekan Meru"
    assert binjai["district"] == "Klang"
    assert binjai["state"] == "SEL"
    assert binjai["source_time"] == datetime(2026, 10, 14, 19, 45)
    assert binjai["wl_m"] == 3.21
    assert (binjai["wl_normal_m"], binjai["wl_alert_m"], binjai["wl_warning_m"], binjai["wl_danger_m"]) == (2.80, 3.80, 4.00, 4.20)


def test_parse_wl_live_returns_every_station_row():
    rows = ib.parse_wl_live(read("infobanjir_wl_live_SEL.html"), state="SEL")
    assert len(rows) == 67
    assert all(r["graph_id"] for r in rows)  # one real station has a blank code


# ---------- live rainfall table (malformed HTML: rows have no <tr>) ----------

def test_parse_rf_live_reads_kg_perepat():
    rows = ib.parse_rf_live(read("infobanjir_rf_live_SEL.html"), state="SEL")
    perepat = next(r for r in rows if r["station_code"] == "0220301RF")
    assert perepat["graph_id"] == "26558"
    assert perepat["station_name"] == "Kg. Perepat, Kapar"
    assert perepat["district"] == "Klang"
    assert perepat["source_time"] == datetime(2026, 10, 14, 20, 15)
    assert perepat["rain_since_midnight_mm"] == 0.0
    assert perepat["rain_1h_mm"] == 0.0
    assert perepat["daily_mm"] == {
        "2026-10-08": 0.0, "2026-10-09": 0.0, "2026-10-10": 1.5,
        "2026-10-11": 0.5, "2026-10-12": 7.5, "2026-10-13": 0.0,
    }


def test_parse_rf_live_maps_daily_columns_to_header_dates():
    rows = ib.parse_rf_live(read("infobanjir_rf_live_SEL.html"), state="SEL")
    pandamaran = next(r for r in rows if r["station_code"] == "3014002")
    assert pandamaran["daily_mm"]["2026-10-10"] == 66.0
    assert all(r["graph_id"] for r in rows)
    assert len(rows) > 200


# ---------- history endpoints ----------

def test_parse_history_handles_no_result_payload():
    assert ib.parse_history(read("infobanjir_hist_empty.txt")) == {"info": {}, "values": []}


def test_parse_history_reads_empty_values_as_missing():
    # Real JPS output, 26558 rain, 5 May 2024: empty values instead of numbers.
    text = ('\n{"info": {"name": "x","count":2},"values":['
            '{"dt":"05/05/2024 20:45","raw":0,"clean":0,"cdaily":0,"cyearly":663.5,"c15min":0},'
            '{"dt":"05/05/2024 20:50","raw":-9999,"clean":-9999,"cdaily":,"tdaily":0,"cyearly":,"c15min":-9999}]}')
    payload = ib.parse_history(text)
    assert len(payload["values"]) == 2
    assert payload["values"][1]["cdaily"] is None


def test_wl_history_keeps_quarter_hours_only_and_reproduces_12_nov_2024():
    payload = ib.parse_history(read("infobanjir_wl_hist_PEKANMERU_20241112.txt"))
    rows = ib.wl_history_rows(payload, graph_id="PEKANMERU")
    assert {r["time_local"].minute for r in rows} <= {0, 15, 30, 45}
    by_time = {r["time_local"]: r["wl_m"] for r in rows}
    assert by_time[datetime(2024, 11, 12, 8, 0)] == 2.94
    assert by_time[datetime(2024, 11, 12, 10, 0)] == 4.21
    peak = max((r for r in rows if r["wl_m"] is not None), key=lambda r: r["wl_m"])
    assert (peak["time_local"], peak["wl_m"]) == (datetime(2024, 11, 12, 11, 45), 4.26)
    assert rows[0]["wl_danger_m"] == 4.2
    assert all(r["wl_m"] is None or r["wl_m"] > -1000 for r in rows)


def test_rf_history_does_not_triple_count_repeated_5min_rows():
    payload = ib.parse_history(read("infobanjir_rf_hist_26558_20241112.txt"))
    rows = ib.rf_history_rows(payload, graph_id="26558")
    assert {r["time_local"].minute for r in rows} <= {0, 15, 30, 45}
    assert sum(r["rain_15min_mm"] or 0 for r in rows) == 79.0
    by_time = {r["time_local"]: r["rain_15min_mm"] for r in rows}
    assert by_time[datetime(2024, 11, 12, 8, 45)] == 31.0
    assert by_time[datetime(2024, 11, 12, 9, 0)] == 16.5


# ---------- request planning ----------

def test_month_chunks_cover_range_in_calendar_months():
    assert ib.month_chunks(date(2024, 1, 1), date(2024, 3, 10)) == [
        ("01/01/2024 00:00", "31/01/2024 23:45"),
        ("01/02/2024 00:00", "29/02/2024 23:45"),
        ("01/03/2024 00:00", "10/03/2024 23:45"),
    ]


def test_is_stale_after_two_hours():
    fetched = datetime(2026, 10, 14, 12, 0)
    assert ib.is_stale(datetime(2026, 10, 14, 9, 59), fetched) is True
    assert ib.is_stale(datetime(2026, 10, 14, 10, 30), fetched) is False
    assert ib.is_stale(None, fetched) is True
