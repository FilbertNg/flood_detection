import pandas as pd

from floodready import stations


def live_wl():
    return pd.DataFrame([
        {"graph_id": "PEKANMERU", "station_code": "3112401", "station_name": "Sg. Binjai di Pekan Meru", "district": "Klang",
         "state": "SEL", "wl_normal_m": 2.8, "wl_alert_m": 3.8, "wl_warning_m": 4.0, "wl_danger_m": 4.2},
        {"graph_id": "26558", "station_code": "0220301WL", "station_name": "Sg. Kapar Kechil di Kg. Perepat, Kapar",
         "district": "Klang", "state": "SEL", "wl_normal_m": 0.0, "wl_alert_m": 0.6, "wl_warning_m": 1.0, "wl_danger_m": 1.5},
    ])


def live_rf():
    return pd.DataFrame([
        {"graph_id": "26558", "station_code": "0220301RF", "station_name": "Kg. Perepat, Kapar", "district": "Klang", "state": "SEL"},
        {"graph_id": "NOWHERE", "station_code": "9999999", "station_name": "Unknown", "district": "Klang", "state": "SEL"},
    ])


def old_api():
    return pd.DataFrame([
        {"station_id": "_PEKANMERU_X", "station_code": "PEKANMERU", "latitude": 3.136456, "longitude": 101.438946},
        {"station_id": "26558", "station_code": "KG PEREPATKAPAR", "latitude": 3.107821, "longitude": 101.355571},
    ])


def test_lookup_has_one_row_per_station_and_kind_with_coordinates():
    lookup = stations.build_lookup(live_wl(), live_rf(), old_api()).set_index(["graph_id", "kind"])
    assert lookup.loc[("26558", "rf"), "name"] == "Kg. Perepat, Kapar"
    assert lookup.loc[("26558", "wl"), "name"] == "Sg. Kapar Kechil di Kg. Perepat, Kapar"
    assert lookup.loc[("26558", "rf"), "lat"] == 3.107821                 # matched on old station_id
    assert lookup.loc[("PEKANMERU", "wl"), "lon"] == 101.438946           # matched on old station_code
    assert lookup.loc[("PEKANMERU", "wl"), "wl_danger_m"] == 4.2
    assert pd.isna(lookup.loc[("NOWHERE", "rf"), "lat"])                  # kept, without coordinates


def test_thresholds_out_of_order_are_flagged():
    wl = live_wl()
    wl.loc[0, "wl_warning_m"] = 3.5                                      # warning below alert
    lookup = stations.build_lookup(wl, live_rf(), old_api()).set_index(["graph_id", "kind"])
    assert bool(lookup.loc[("PEKANMERU", "wl"), "thresholds_ok"]) is False
    assert bool(lookup.loc[("26558", "wl"), "thresholds_ok"]) is True
