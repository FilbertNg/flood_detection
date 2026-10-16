# Data QC report

Generated 16 Oct 2026 by `scripts/qc_report.py` on the JPS history archive as it stands today: 100 rain gauges and 15 river stations, 9,555,759 15-min rows, 2024-01-01 to 2026-10-16 (archive progress 113/311 station series). **The archive is still being filled; this report will be regenerated when it finishes** (`python scripts/qc_report.py`).

Rules live in `floodready/qc.py` and run inside `engine/replay.py::load_archive_readings` and `live.py::load_live_readings`, so replay, training, the API and live data all see the cleaned values. A flagged value becomes NaN, never 0.

**Live mode:** `wl_spike` and `rain_after_gap` need the next reading. A gauge's latest reading is kept and judged when the next one arrives, so a real rise or storm after an outage is never hidden. Archive cleaning (replay, training) sees the reading at t+15 min, live cleaning does not: a small train/serve difference, limited to the latest reading of each gauge.

## 1. Summary

| rule | readings | stations | rule_text |
| --- | --- | --- | --- |
| rain_negative | 53 | 37 | rain < 0 (a counter cannot go down: 1 Jan reset, gauge restart) |
| rain_implausible | 116 | 39 | rain > 100 mm per 15 min (> 400 mm/h) |
| rain_counter_rebound | 2 | 1 | a positive reading within 24 h after a dip of <= -5 mm at the same gauge, equal to the dip within max(1 mm, 5 %): the counter dipped and was restored |
| rain_after_gap | 7 | 6 | rain >= 30 mm in the first reading after >= 2 h without readings, unless the next reading is >= 10 mm and different (a storm that continues); an identical repeat right after is removed too. A gauge's latest reading is kept until the next arrives |
| rain_stuck | 6 | 2 | the same value >= 20 mm at least 3 times within 24 h at one gauge (only readings not already removed by the rules above) |
| wl_spike | 132 | 9 | river level more than 1 m from both neighbours in the same direction, with the neighbours within max(0.2 m, half the jump) of each other. A station's latest reading is kept until the next arrives |
| wl_unresponsive | 12644 | 9 | river level within 1.5 cm for >= 3 h while rain at the gauges within 10 km totals >= 30 mm over the same window (largest rolling sum over those gauges). Flagged from the first reading where both hold until the level moves again; a flat level alone is base flow and is kept |

184 of 7,086,356 rain readings (0.0026%) and 12776 river readings removed.

Thresholds: the largest rain value kept is 100 mm per 15 min; the values removed by `rain_implausible` range from 120 to 2981.5 mm. `rain_after_gap` needs the continuation test (section 3): without it it removed readings of storms that began during a gap.

## 2. Flagged readings by rule and station

### `rain_negative`: 53 readings, 37 stations

rain < 0 (a counter cannot go down: 1 Jan reset, gauge restart).

| graph_id | name | count | min_value | max_value | first | last |
| --- | --- | --- | --- | --- | --- | --- |
| 26377 | Sentul Park (F2) | 9 | -13.5 | -0.5 | 2024-01-01 14:30 | 2025-02-19 12:30 |
| 3117006_ | Kolam Takungan Batu | 6 | -29997.0 | -19998.0 | 2026-08-12 14:15 | 2026-08-12 15:30 |
| 26352 | Sri Rampai (F2) | 3 | -59.0 | -38.5 | 2024-07-09 09:45 | 2025-11-28 15:30 |
| 26425 | Sek. Men. Agama Kuala Lumpur Bandar Manjalara (F2) | 2 | -2981.5 | -294.5 | 2024-12-18 09:45 | 2025-02-14 11:15 |
| 2414401_ | SMK Jalan Kebun | 1 | -2484.0 | -2484.0 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 26038 | Taman Sentosa | 1 | -2500.5 | -2500.5 | 2024-01-01 00:45 | 2024-01-01 00:45 |
| 26039 | Kg. Budiman | 1 | -1979.5 | -1979.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 26403 | Kg. Padang Balang (F2) | 1 | -2747.5 | -2747.5 | 2024-12-30 16:45 | 2024-12-30 16:45 |
| 26382 | Razak Mansion (F2) | 1 | -0.5 | -0.5 | 2024-08-11 06:45 | 2024-08-11 06:45 |
| 26507 | Empangan Batu (F2) | 1 | -8757.0 | -8757.0 | 2024-07-05 17:00 | 2024-07-05 17:00 |
| 2915118_ | Ayer Hitam Puchong | 1 | -2629.5 | -2629.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3014080_ | Bandar Klang | 1 | -2281.0 | -2281.0 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 26405 | Taman Damai Murni (F2) | 1 | -529.5 | -529.5 | 2025-02-25 11:30 | 2025-02-25 11:30 |
| 3015083_ | TTDI Jaya | 1 | -2336.5 | -2336.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3015084_ | Taman Sri Muda | 1 | -2320.5 | -2320.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3015087_ | Batu 3 | 1 | -2804.5 | -2804.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3015089_ | Tugu Keris | 1 | -2497.5 | -2497.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3016002_ | Jambatan Petaling | 1 | -0.5 | -0.5 | 2025-06-10 10:45 | 2025-06-10 10:45 |
| 3016080_ | Kg. Gandhi | 1 | -3274.5 | -3274.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3017107_ | Seri Kembangan | 1 | -2684.0 | -2684.0 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3015001_ | Puchong Drop | 1 | -2603.5 | -2603.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3114087_ | Empangan Tasik Subang Meru | 1 | -2444.0 | -2444.0 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3115080_ | Paya Jaras | 1 | -3115.5 | -3115.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3115084_ | Kg. Melayu Subang | 1 | -2639.5 | -2639.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3115083_ | Taman Mayang | 1 | -3131.5 | -3131.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3116074_ | Leboh Pasar | 1 | -494.0 | -494.0 | 2024-08-09 16:15 | 2024-08-09 16:15 |
| 3216007_ | Taman Ehsan | 1 | -1.0 | -1.0 | 2024-11-20 20:00 | 2024-11-20 20:00 |
| DESAKEMUNING | Taman Desa Kemuning | 1 | -2623.5 | -2623.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| KGDELEK | Kg. Delek | 1 | -1624.0 | -1624.0 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| KGRANTAUPANJANG | Kg. Rantau Panjang | 1 | -2718.0 | -2718.0 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| KOTADAMANSARA | Kota Damansara | 1 | -2967.5 | -2967.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| PEKANMERU | Pekan Meru | 1 | -2131.0 | -2131.0 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| SELATMUARA | Selat Muara | 1 | -2364.5 | -2364.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| SMKRAJALUMU | SMK Raja Lumu | 1 | -2058.0 | -2058.0 | 2024-01-01 00:45 | 2024-01-01 00:45 |
| TAMANBOTANI | Taman Botani | 1 | -2812.5 | -2812.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| TELOKGONG | Telok Gong | 1 | -1642.0 | -1642.0 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| USJ1 | USJ 1 | 1 | -3312.5 | -3312.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |

<details><summary>Every flagged reading</summary>

| graph_id | time_local | value |
| --- | --- | --- |
| 2414401_ | 2024-01-01 00:15 | -2484.0 |
| 26038 | 2024-01-01 00:45 | -2500.5 |
| 26039 | 2024-01-01 00:15 | -1979.5 |
| 26352 | 2024-07-09 09:45 | -57.0 |
| 26352 | 2025-01-13 13:30 | -38.5 |
| 26352 | 2025-11-28 15:30 | -59.0 |
| 26377 | 2024-01-01 14:30 | -1.0 |
| 26377 | 2024-01-01 17:15 | -0.5 |
| 26377 | 2024-01-02 14:30 | -1.0 |
| 26377 | 2024-01-02 17:15 | -0.5 |
| 26377 | 2024-01-03 14:30 | -1.0 |
| 26377 | 2024-01-05 14:30 | -1.0 |
| 26377 | 2024-01-05 17:15 | -0.5 |
| 26377 | 2024-01-24 15:30 | -0.5 |
| 26377 | 2025-02-19 12:30 | -13.5 |
| 26382 | 2024-08-11 06:45 | -0.5 |
| 26403 | 2024-12-30 16:45 | -2747.5 |
| 26405 | 2025-02-25 11:30 | -529.5 |
| 26425 | 2024-12-18 09:45 | -2981.5 |
| 26425 | 2025-02-14 11:15 | -294.5 |
| 26507 | 2024-07-05 17:00 | -8757.0 |
| 2915118_ | 2024-01-01 00:15 | -2629.5 |
| 3014080_ | 2024-01-01 00:15 | -2281.0 |
| 3015001_ | 2024-01-01 00:15 | -2603.5 |
| 3015083_ | 2024-01-01 00:15 | -2336.5 |
| 3015084_ | 2024-01-01 00:15 | -2320.5 |
| 3015087_ | 2024-01-01 00:15 | -2804.5 |
| 3015089_ | 2024-01-01 00:15 | -2497.5 |
| 3016002_ | 2025-06-10 10:45 | -0.5 |
| 3016080_ | 2024-01-01 00:15 | -3274.5 |
| 3017107_ | 2024-01-01 00:15 | -2684.0 |
| 3114087_ | 2024-01-01 00:15 | -2444.0 |
| 3115080_ | 2024-01-01 00:15 | -3115.5 |
| 3115083_ | 2024-01-01 00:15 | -3131.5 |
| 3115084_ | 2024-01-01 00:15 | -2639.5 |
| 3116074_ | 2024-08-09 16:15 | -494.0 |
| 3117006_ | 2026-08-12 14:15 | -29997.0 |
| 3117006_ | 2026-08-12 14:30 | -29997.0 |
| 3117006_ | 2026-08-12 14:45 | -29997.0 |
| 3117006_ | 2026-08-12 15:00 | -29997.0 |
| 3117006_ | 2026-08-12 15:15 | -29997.0 |
| 3117006_ | 2026-08-12 15:30 | -19998.0 |
| 3216007_ | 2024-11-20 20:00 | -1.0 |
| DESAKEMUNING | 2024-01-01 00:15 | -2623.5 |
| KGDELEK | 2024-01-01 00:15 | -1624.0 |
| KGRANTAUPANJANG | 2024-01-01 00:15 | -2718.0 |
| KOTADAMANSARA | 2024-01-01 00:15 | -2967.5 |
| PEKANMERU | 2024-01-01 00:15 | -2131.0 |
| SELATMUARA | 2024-01-01 00:15 | -2364.5 |
| SMKRAJALUMU | 2024-01-01 00:45 | -2058.0 |
| TAMANBOTANI | 2024-01-01 00:15 | -2812.5 |
| TELOKGONG | 2024-01-01 00:15 | -1642.0 |
| USJ1 | 2024-01-01 00:15 | -3312.5 |

</details>

### `rain_implausible`: 116 readings, 39 stations

rain > 100 mm per 15 min (> 400 mm/h).

| graph_id | name | count | min_value | max_value | first | last |
| --- | --- | --- | --- | --- | --- | --- |
| 27879 | Jalan SS 2/24 (F2) | 30 | 287.5 | 296.5 | 2025-11-06 15:15 | 2025-11-09 20:45 |
| 26405 | Taman Damai Murni (F2) | 10 | 120.0 | 529.5 | 2024-04-30 16:15 | 2025-03-25 11:00 |
| 26502 | JPS Wilayah (F2) | 6 | 893.5 | 1458.0 | 2024-08-09 12:30 | 2025-06-10 13:15 |
| 26507 | Empangan Batu (F2) | 5 | 365.0 | 365.5 | 2024-08-09 13:00 | 2024-08-09 16:30 |
| 26382 | Razak Mansion (F2) | 4 | 538.5 | 1618.0 | 2024-08-26 17:15 | 2026-07-20 14:15 |
| 26385 | Sek. Men. Keb. Wangsa Maju Seksyen 2 (F2) | 4 | 803.5 | 1034.0 | 2024-06-25 09:30 | 2024-08-20 11:30 |
| 3017107_ | Seri Kembangan | 4 | 578.5 | 597.5 | 2026-05-01 12:45 | 2026-06-25 18:45 |
| 3015440_ | IOI Puchong Jaya | 3 | 1895.5 | 2191.0 | 2025-11-21 01:00 | 2025-12-16 00:00 |
| 3015084_ | Taman Sri Muda | 3 | 1756.5 | 2187.5 | 2025-10-17 00:00 | 2025-12-20 00:00 |
| 3115080_ | Paya Jaras | 3 | 1301.5 | 2185.0 | 2025-07-29 00:00 | 2025-12-25 00:00 |
| 26420 | Kg. Muda (F2) | 3 | 558.0 | 1351.0 | 2024-07-11 12:15 | 2024-11-22 11:00 |
| BTU10_ | Kg. Batu Muda (F2) | 3 | 1065.5 | 1250.0 | 2024-06-24 11:15 | 2025-05-07 13:15 |
| 26425 | Sek. Men. Agama Kuala Lumpur Bandar Manjalara (F2) | 3 | 294.5 | 2981.5 | 2024-06-26 15:45 | 2025-02-14 12:15 |
| 2915118_ | Ayer Hitam Puchong | 3 | 230.0 | 436.0 | 2026-04-23 09:30 | 2026-06-25 17:15 |
| 3015087_ | Batu 3 | 3 | 641.5 | 2050.5 | 2024-11-04 00:00 | 2025-10-28 00:00 |
| KOTADAMANSARA | Kota Damansara | 3 | 256.5 | 1388.0 | 2024-08-28 11:15 | 2024-09-11 16:15 |
| TAMANBOTANI | Taman Botani | 2 | 2179.5 | 2364.5 | 2025-12-06 00:00 | 2025-12-20 00:00 |
| 26403 | Kg. Padang Balang (F2) | 2 | 1675.5 | 2747.5 | 2024-12-30 17:45 | 2026-06-30 16:45 |
| 3016002_ | Jambatan Petaling | 2 | 274.0 | 274.0 | 2024-08-15 12:00 | 2024-08-15 14:30 |
| 26039 | Kg. Budiman | 1 | 244.5 | 244.5 | 2024-02-14 20:30 | 2024-02-14 20:30 |
| 26377 | Sentul Park (F2) | 1 | 745.5 | 745.5 | 2026-07-03 15:30 | 2026-07-03 15:30 |
| 26350 | Jalan Ang Seng (F2) | 1 | 1726.0 | 1726.0 | 2024-06-25 10:45 | 2024-06-25 10:45 |
| 26371 | Sek. Men. Aminuddin Baki (F2) | 1 | 1675.5 | 1675.5 | 2024-11-02 02:15 | 2024-11-02 02:15 |
| 26393 | Segambut Bahagia TNB (F2) | 1 | 2821.5 | 2821.5 | 2024-11-22 11:00 | 2024-11-22 11:00 |
| 3015083_ | TTDI Jaya | 1 | 1864.5 | 1864.5 | 2025-11-21 00:00 | 2025-11-21 00:00 |
| 26414 | Kolam Takungan Banjir Sg. Midah (F2) | 1 | 1475.5 | 1475.5 | 2024-06-24 16:15 | 2024-06-24 16:15 |
| 27233 | Kg. Lombong | 1 | 2569.5 | 2569.5 | 2025-12-20 03:00 | 2025-12-20 03:00 |
| 27859 | Emp. Tasik Subang Meru (F2) | 1 | 421.0 | 421.0 | 2025-12-22 14:30 | 2025-12-22 14:30 |
| 3115083_ | Taman Mayang | 1 | 574.5 | 574.5 | 2026-04-23 12:00 | 2026-04-23 12:00 |
| 3016080_ | Kg. Gandhi | 1 | 1871.0 | 1871.0 | 2025-12-20 03:00 | 2025-12-20 03:00 |
| 3114005_ | Lembah Keramat | 1 | 321.5 | 321.5 | 2024-08-15 12:45 | 2024-08-15 12:45 |
| 3116074_ | Leboh Pasar | 1 | 494.0 | 494.0 | 2024-08-09 16:30 | 2024-08-09 16:30 |
| 3116006_ | Ladang Edinburgh | 1 | 1562.5 | 1562.5 | 2024-08-15 12:30 | 2024-08-15 12:30 |
| 3116004_ | JPS Wilayah | 1 | 897.5 | 897.5 | 2024-08-15 12:45 | 2024-08-15 12:45 |
| 3117070_ | JPS Ampang | 1 | 121.5 | 121.5 | 2024-08-15 12:45 | 2024-08-15 12:45 |
| KGRANTAUPANJANG | Kg. Rantau Panjang | 1 | 1693.0 | 1693.0 | 2025-11-21 00:00 | 2025-11-21 00:00 |
| KGDELEK | Kg. Delek | 1 | 1487.5 | 1487.5 | 2025-11-21 00:00 | 2025-11-21 00:00 |
| PANDAMARAN | P/A Pandamaran | 1 | 1697.0 | 1697.0 | 2025-12-17 00:00 | 2025-12-17 00:00 |
| USJ1 | USJ 1 | 1 | 1508.0 | 1508.0 | 2025-10-31 00:15 | 2025-10-31 00:15 |

<details><summary>Every flagged reading</summary>

| graph_id | time_local | value |
| --- | --- | --- |
| 26039 | 2024-02-14 20:30 | 244.5 |
| 26350 | 2024-06-25 10:45 | 1726.0 |
| 26371 | 2024-11-02 02:15 | 1675.5 |
| 26377 | 2026-07-03 15:30 | 745.5 |
| 26382 | 2024-08-26 17:15 | 1288.5 |
| 26382 | 2025-03-03 13:00 | 538.5 |
| 26382 | 2025-07-31 15:15 | 1618.0 |
| 26382 | 2026-07-20 14:15 | 1417.0 |
| 26385 | 2024-06-25 09:30 | 803.5 |
| 26385 | 2024-07-02 16:15 | 934.5 |
| 26385 | 2024-08-13 10:30 | 953.5 |
| 26385 | 2024-08-20 11:30 | 1034.0 |
| 26393 | 2024-11-22 11:00 | 2821.5 |
| 26403 | 2024-12-30 17:45 | 2747.5 |
| 26403 | 2026-06-30 16:45 | 1675.5 |
| 26405 | 2024-04-30 16:15 | 140.0 |
| 26405 | 2024-04-30 16:30 | 120.0 |
| 26405 | 2024-05-01 16:15 | 175.0 |
| 26405 | 2024-05-01 19:45 | 125.0 |
| 26405 | 2024-05-13 16:15 | 340.0 |
| 26405 | 2024-05-13 16:30 | 130.0 |
| 26405 | 2024-06-27 11:00 | 165.0 |
| 26405 | 2025-02-25 13:00 | 529.5 |
| 26405 | 2025-03-25 10:30 | 163.5 |
| 26405 | 2025-03-25 11:00 | 491.5 |
| 26414 | 2024-06-24 16:15 | 1475.5 |
| 26420 | 2024-07-11 12:15 | 558.0 |
| 26420 | 2024-08-17 10:15 | 579.0 |
| 26420 | 2024-11-22 11:00 | 1351.0 |
| 26425 | 2024-06-26 15:45 | 1455.5 |
| 26425 | 2024-12-18 11:15 | 2981.5 |
| 26425 | 2025-02-14 12:15 | 294.5 |
| 26502 | 2024-08-09 12:30 | 893.5 |
| 26502 | 2024-08-09 13:00 | 893.5 |
| 26502 | 2024-08-09 14:45 | 893.5 |
| 26502 | 2024-08-09 15:15 | 893.5 |
| 26502 | 2024-08-09 16:15 | 893.5 |
| 26502 | 2025-06-10 13:15 | 1458.0 |
| 26507 | 2024-08-09 13:00 | 365.0 |
| 26507 | 2024-08-09 13:45 | 365.0 |
| 26507 | 2024-08-09 14:15 | 365.5 |
| 26507 | 2024-08-09 15:15 | 365.5 |
| 26507 | 2024-08-09 16:30 | 365.5 |
| 27233 | 2025-12-20 03:00 | 2569.5 |
| 27859 | 2025-12-22 14:30 | 421.0 |
| 27879 | 2025-11-06 15:15 | 296.5 |
| 27879 | 2025-11-06 23:15 | 296.5 |
| 27879 | 2025-11-07 00:15 | 296.5 |
| 27879 | 2025-11-07 01:15 | 296.5 |
| 27879 | 2025-11-07 03:30 | 296.5 |
| 27879 | 2025-11-07 04:30 | 296.5 |
| 27879 | 2025-11-07 06:15 | 296.5 |
| 27879 | 2025-11-07 09:30 | 287.5 |
| 27879 | 2025-11-07 11:15 | 287.5 |
| 27879 | 2025-11-07 14:00 | 287.5 |
| 27879 | 2025-11-07 15:30 | 287.5 |
| 27879 | 2025-11-07 17:30 | 287.5 |
| 27879 | 2025-11-07 18:15 | 287.5 |
| 27879 | 2025-11-07 20:00 | 287.5 |
| 27879 | 2025-11-08 01:00 | 287.5 |
| 27879 | 2025-11-08 04:00 | 287.5 |
| 27879 | 2025-11-08 04:30 | 287.5 |
| 27879 | 2025-11-08 06:15 | 287.5 |
| 27879 | 2025-11-08 09:45 | 287.5 |
| 27879 | 2025-11-08 16:15 | 287.5 |
| 27879 | 2025-11-08 23:45 | 287.5 |
| 27879 | 2025-11-09 09:00 | 287.5 |
| 27879 | 2025-11-09 14:15 | 287.5 |
| 27879 | 2025-11-09 15:00 | 287.5 |
| 27879 | 2025-11-09 15:45 | 287.5 |
| 27879 | 2025-11-09 16:45 | 287.5 |
| 27879 | 2025-11-09 17:45 | 287.5 |
| 27879 | 2025-11-09 19:00 | 287.5 |
| 27879 | 2025-11-09 19:45 | 287.5 |
| 27879 | 2025-11-09 20:45 | 287.5 |
| 2915118_ | 2026-04-23 09:30 | 230.0 |
| 2915118_ | 2026-05-05 09:00 | 230.0 |
| 2915118_ | 2026-06-25 17:15 | 436.0 |
| 3015083_ | 2025-11-21 00:00 | 1864.5 |
| 3015084_ | 2025-10-17 00:00 | 1756.5 |
| 3015084_ | 2025-11-21 09:00 | 1849.0 |
| 3015084_ | 2025-12-20 00:00 | 2187.5 |
| 3015087_ | 2024-11-04 00:00 | 2050.5 |
| 3015087_ | 2025-07-05 00:15 | 641.5 |
| 3015087_ | 2025-10-28 00:00 | 964.0 |
| 3015440_ | 2025-11-21 01:00 | 1895.5 |
| 3015440_ | 2025-12-05 00:00 | 2191.0 |
| 3015440_ | 2025-12-16 00:00 | 2185.5 |
| 3016002_ | 2024-08-15 12:00 | 274.0 |
| 3016002_ | 2024-08-15 14:30 | 274.0 |
| 3016080_ | 2025-12-20 03:00 | 1871.0 |
| 3017107_ | 2026-05-01 12:45 | 578.5 |
| 3017107_ | 2026-05-08 20:00 | 597.5 |
| 3017107_ | 2026-06-21 21:15 | 587.0 |
| 3017107_ | 2026-06-25 18:45 | 589.5 |
| 3114005_ | 2024-08-15 12:45 | 321.5 |
| 3115080_ | 2025-07-29 00:00 | 1301.5 |
| 3115080_ | 2025-11-21 01:00 | 1796.5 |
| 3115080_ | 2025-12-25 00:00 | 2185.0 |
| 3115083_ | 2026-04-23 12:00 | 574.5 |
| 3116004_ | 2024-08-15 12:45 | 897.5 |
| 3116006_ | 2024-08-15 12:30 | 1562.5 |
| 3116074_ | 2024-08-09 16:30 | 494.0 |
| 3117070_ | 2024-08-15 12:45 | 121.5 |
| BTU10_ | 2024-06-24 11:15 | 1168.0 |
| BTU10_ | 2024-07-11 10:15 | 1250.0 |
| BTU10_ | 2025-05-07 13:15 | 1065.5 |
| KGDELEK | 2025-11-21 00:00 | 1487.5 |
| KGRANTAUPANJANG | 2025-11-21 00:00 | 1693.0 |
| KOTADAMANSARA | 2024-08-28 11:15 | 256.5 |
| KOTADAMANSARA | 2024-08-28 11:30 | 1388.0 |
| KOTADAMANSARA | 2024-09-11 16:15 | 1388.0 |
| PANDAMARAN | 2025-12-17 00:00 | 1697.0 |
| TAMANBOTANI | 2025-12-06 00:00 | 2179.5 |
| TAMANBOTANI | 2025-12-20 00:00 | 2364.5 |
| USJ1 | 2025-10-31 00:15 | 1508.0 |

</details>

### `rain_counter_rebound`: 2 readings, 1 stations

a positive reading within 24 h after a dip of <= -5 mm at the same gauge, equal to the dip within max(1 mm, 5 %): the counter dipped and was restored.

| graph_id | name | count | min_value | max_value | first | last |
| --- | --- | --- | --- | --- | --- | --- |
| 26352 | Sri Rampai (F2) | 2 | 38.5 | 56.5 | 2024-07-09 11:30 | 2025-01-14 09:30 |

<details><summary>Every flagged reading</summary>

| graph_id | time_local | value |
| --- | --- | --- |
| 26352 | 2024-07-09 11:30 | 56.5 |
| 26352 | 2025-01-14 09:30 | 38.5 |

</details>

### `rain_after_gap`: 7 readings, 6 stations

rain >= 30 mm in the first reading after >= 2 h without readings, unless the next reading is >= 10 mm and different (a storm that continues); an identical repeat right after is removed too. A gauge's latest reading is kept until the next arrives.

| graph_id | name | count | min_value | max_value | first | last |
| --- | --- | --- | --- | --- | --- | --- |
| 3115080_ | Paya Jaras | 2 | 61.0 | 61.0 | 2025-04-28 15:30 | 2025-04-28 15:45 |
| 26352 | Sri Rampai (F2) | 1 | 36.0 | 36.0 | 2024-07-04 14:45 | 2024-07-04 14:45 |
| 26382 | Razak Mansion (F2) | 1 | 47.0 | 47.0 | 2024-01-23 18:45 | 2024-01-23 18:45 |
| 27397 | KDR Sandaran Permai (F2) | 1 | 46.0 | 46.0 | 2026-09-26 08:45 | 2026-09-26 08:45 |
| 3116074_ | Leboh Pasar | 1 | 38.0 | 38.0 | 2025-06-11 00:15 | 2025-06-11 00:15 |
| BTU10_ | Kg. Batu Muda (F2) | 1 | 31.0 | 31.0 | 2024-03-23 21:30 | 2024-03-23 21:30 |

<details><summary>Every flagged reading</summary>

| graph_id | time_local | value |
| --- | --- | --- |
| 26352 | 2024-07-04 14:45 | 36.0 |
| 26382 | 2024-01-23 18:45 | 47.0 |
| 27397 | 2026-09-26 08:45 | 46.0 |
| 3115080_ | 2025-04-28 15:30 | 61.0 |
| 3115080_ | 2025-04-28 15:45 | 61.0 |
| 3116074_ | 2025-06-11 00:15 | 38.0 |
| BTU10_ | 2024-03-23 21:30 | 31.0 |

</details>

### `rain_stuck`: 6 readings, 2 stations

the same value >= 20 mm at least 3 times within 24 h at one gauge (only readings not already removed by the rules above).

| graph_id | name | count | min_value | max_value | first | last |
| --- | --- | --- | --- | --- | --- | --- |
| 26405 | Taman Damai Murni (F2) | 3 | 25.0 | 25.0 | 2024-05-11 18:00 | 2024-05-11 19:00 |
| 26506 | Kg. Cheras Baru (F2) | 3 | 32.5 | 32.5 | 2024-08-09 14:45 | 2024-08-09 16:15 |

<details><summary>Every flagged reading</summary>

| graph_id | time_local | value |
| --- | --- | --- |
| 26405 | 2024-05-11 18:00 | 25.0 |
| 26405 | 2024-05-11 18:45 | 25.0 |
| 26405 | 2024-05-11 19:00 | 25.0 |
| 26506 | 2024-08-09 14:45 | 32.5 |
| 26506 | 2024-08-09 15:45 | 32.5 |
| 26506 | 2024-08-09 16:15 | 32.5 |

</details>

### `wl_spike`: 132 readings, 9 stations

river level more than 1 m from both neighbours in the same direction, with the neighbours within max(0.2 m, half the jump) of each other. A station's latest reading is kept until the next arrives.

| graph_id | name | count | min_value | max_value | first | last |
| --- | --- | --- | --- | --- | --- | --- |
| 3115080_ | Paya Jaras | 75 | 12.14 | 18.49 | 2024-04-01 05:00 | 2025-12-01 14:00 |
| 3115084_ | Kg. Melayu Subang | 25 | 12.64 | 17.44 | 2024-05-23 02:00 | 2026-04-26 23:45 |
| 3115083_ | Taman Mayang | 9 | 13.75 | 18.94 | 2024-06-01 10:45 | 2024-08-13 14:00 |
| 3014080_ | Bandar Klang | 7 | -6.58 | 0.69 | 2024-04-10 19:15 | 2024-09-20 07:45 |
| 3015084_ | Taman Sri Muda | 6 | -1.22 | 3.98 | 2024-04-09 14:15 | 2026-08-12 13:00 |
| 3015083_ | TTDI Jaya | 4 | 1.67 | 2.71 | 2024-06-18 04:00 | 2024-10-04 08:45 |
| 3016080_ | Kg. Gandhi | 3 | 4.92 | 13.6 | 2024-04-22 16:45 | 2024-07-05 12:45 |
| 3015089_ | Tugu Keris | 2 | 2.85 | 2.92 | 2025-10-14 05:15 | 2026-05-22 18:30 |
| 3017107_ | Seri Kembangan | 1 | 37.65 | 37.65 | 2024-07-07 21:15 | 2024-07-07 21:15 |

<details><summary>Every flagged reading</summary>

| graph_id | time_local | value |
| --- | --- | --- |
| 3014080_ | 2024-04-10 19:15 | -0.45 |
| 3014080_ | 2024-05-10 07:15 | -6.58 |
| 3014080_ | 2024-06-06 17:45 | -6.27 |
| 3014080_ | 2024-08-23 18:45 | -5.85 |
| 3014080_ | 2024-09-04 05:30 | -2.65 |
| 3014080_ | 2024-09-15 04:30 | -4.12 |
| 3014080_ | 2024-09-20 07:45 | 0.69 |
| 3015083_ | 2024-06-18 04:00 | 2.71 |
| 3015083_ | 2024-07-10 12:45 | 2.17 |
| 3015083_ | 2024-08-08 04:15 | 1.67 |
| 3015083_ | 2024-10-04 08:45 | 2.27 |
| 3015084_ | 2024-04-09 14:15 | 2.89 |
| 3015084_ | 2024-05-08 21:15 | 0.78 |
| 3015084_ | 2025-08-23 15:15 | -1.22 |
| 3015084_ | 2026-04-23 10:30 | 3.21 |
| 3015084_ | 2026-07-09 18:00 | 3.98 |
| 3015084_ | 2026-08-12 13:00 | 1.83 |
| 3015089_ | 2025-10-14 05:15 | 2.92 |
| 3015089_ | 2026-05-22 18:30 | 2.85 |
| 3016080_ | 2024-04-22 16:45 | 13.08 |
| 3016080_ | 2024-05-15 16:45 | 4.92 |
| 3016080_ | 2024-07-05 12:45 | 13.6 |
| 3017107_ | 2024-07-07 21:15 | 37.65 |
| 3115080_ | 2024-04-01 05:00 | 13.45 |
| 3115080_ | 2024-04-01 09:15 | 16.91 |
| 3115080_ | 2024-04-01 10:30 | 16.93 |
| 3115080_ | 2024-04-01 18:00 | 17.55 |
| 3115080_ | 2024-04-01 18:15 | 14.69 |
| 3115080_ | 2024-04-01 23:00 | 13.4 |
| 3115080_ | 2024-04-02 05:15 | 18.17 |
| 3115080_ | 2024-04-02 05:45 | 13.39 |
| 3115080_ | 2024-04-02 07:15 | 17.25 |
| 3115080_ | 2024-04-02 18:00 | 13.39 |
| 3115080_ | 2024-04-02 19:15 | 13.41 |
| 3115080_ | 2024-04-02 21:15 | 13.38 |
| 3115080_ | 2024-04-03 00:15 | 17.63 |
| 3115080_ | 2024-04-03 00:45 | 15.09 |
| 3115080_ | 2024-04-03 01:30 | 13.48 |
| 3115080_ | 2024-04-03 03:00 | 13.59 |
| 3115080_ | 2024-04-03 04:45 | 13.39 |
| 3115080_ | 2024-04-03 10:15 | 13.4 |
| 3115080_ | 2024-04-03 15:15 | 18.1 |
| 3115080_ | 2024-04-03 16:45 | 15.72 |
| 3115080_ | 2024-04-11 12:45 | 16.31 |
| 3115080_ | 2024-04-11 14:15 | 17.09 |
| 3115080_ | 2024-05-14 01:15 | 16.71 |
| 3115080_ | 2024-05-17 17:45 | 12.67 |
| 3115080_ | 2024-05-17 18:45 | 12.14 |
| 3115080_ | 2024-05-18 17:45 | 15.29 |
| 3115080_ | 2024-05-18 18:30 | 15.97 |
| 3115080_ | 2024-05-18 20:00 | 14.57 |
| 3115080_ | 2024-05-18 20:45 | 13.62 |
| 3115080_ | 2024-05-18 21:00 | 18.28 |
| 3115080_ | 2024-05-18 21:15 | 13.29 |
| 3115080_ | 2024-05-19 12:45 | 15.79 |
| 3115080_ | 2024-05-19 19:30 | 12.23 |
| 3115080_ | 2024-05-20 10:45 | 12.87 |
| 3115080_ | 2024-05-20 13:15 | 13.91 |
| 3115080_ | 2024-05-20 17:00 | 14.27 |
| 3115080_ | 2024-05-20 17:30 | 16.29 |
| 3115080_ | 2024-05-21 12:15 | 16.8 |
| 3115080_ | 2024-05-24 17:45 | 14.66 |
| 3115080_ | 2024-05-26 13:00 | 16.8 |
| 3115080_ | 2024-05-27 14:00 | 14.52 |
| 3115080_ | 2024-05-28 16:00 | 13.64 |
| 3115080_ | 2024-05-29 02:45 | 15.01 |
| 3115080_ | 2024-06-05 13:30 | 13.79 |
| 3115080_ | 2024-06-07 02:00 | 12.82 |
| 3115080_ | 2024-06-07 13:00 | 16.0 |
| 3115080_ | 2024-06-07 13:15 | 18.41 |
| 3115080_ | 2024-06-07 13:30 | 16.1 |
| 3115080_ | 2024-06-10 13:15 | 17.34 |
| 3115080_ | 2024-06-10 20:30 | 14.97 |
| 3115080_ | 2024-06-12 13:00 | 15.06 |
| 3115080_ | 2024-06-15 12:45 | 14.86 |
| 3115080_ | 2024-06-23 14:45 | 13.58 |
| 3115080_ | 2024-06-23 15:30 | 18.43 |
| 3115080_ | 2024-06-23 15:45 | 14.68 |
| 3115080_ | 2024-06-23 16:00 | 18.49 |
| 3115080_ | 2024-06-23 16:15 | 15.63 |
| 3115080_ | 2024-06-23 18:00 | 16.55 |
| 3115080_ | 2024-06-23 23:45 | 15.15 |
| 3115080_ | 2024-06-24 12:15 | 17.19 |
| 3115080_ | 2024-06-24 17:15 | 15.01 |
| 3115080_ | 2024-06-25 15:15 | 14.11 |
| 3115080_ | 2024-06-25 17:30 | 14.01 |
| 3115080_ | 2024-06-25 22:00 | 15.3 |
| 3115080_ | 2024-07-09 00:00 | 14.83 |
| 3115080_ | 2025-10-28 16:00 | 16.66 |
| 3115080_ | 2025-10-28 16:15 | 17.91 |
| 3115080_ | 2025-10-28 16:30 | 16.24 |
| 3115080_ | 2025-10-29 00:15 | 16.37 |
| 3115080_ | 2025-10-29 16:00 | 16.41 |
| 3115080_ | 2025-10-30 13:30 | 16.25 |
| 3115080_ | 2025-10-30 13:45 | 17.93 |
| 3115080_ | 2025-10-30 20:00 | 16.26 |
| 3115080_ | 2025-10-31 22:00 | 15.99 |
| 3115080_ | 2025-12-01 14:00 | 18.37 |
| 3115083_ | 2024-06-01 10:45 | 13.75 |
| 3115083_ | 2024-07-08 00:45 | 13.81 |
| 3115083_ | 2024-08-05 11:45 | 17.0 |
| 3115083_ | 2024-08-06 14:15 | 17.58 |
| 3115083_ | 2024-08-06 15:00 | 18.94 |
| 3115083_ | 2024-08-10 14:45 | 17.42 |
| 3115083_ | 2024-08-13 11:45 | 17.61 |
| 3115083_ | 2024-08-13 13:45 | 17.57 |
| 3115083_ | 2024-08-13 14:00 | 14.86 |
| 3115084_ | 2024-05-23 02:00 | 12.64 |
| 3115084_ | 2024-08-22 14:00 | 12.8 |
| 3115084_ | 2024-09-01 10:00 | 16.4 |
| 3115084_ | 2024-09-02 09:00 | 16.89 |
| 3115084_ | 2024-09-02 13:45 | 16.78 |
| 3115084_ | 2024-09-02 19:45 | 17.25 |
| 3115084_ | 2024-09-02 23:15 | 14.71 |
| 3115084_ | 2024-09-03 00:45 | 14.72 |
| 3115084_ | 2024-09-03 09:15 | 17.44 |
| 3115084_ | 2024-09-03 12:15 | 14.6 |
| 3115084_ | 2024-09-04 03:45 | 17.39 |
| 3115084_ | 2024-09-05 02:00 | 17.39 |
| 3115084_ | 2024-09-05 03:15 | 16.36 |
| 3115084_ | 2024-09-05 07:45 | 17.31 |
| 3115084_ | 2024-09-05 08:00 | 14.67 |
| 3115084_ | 2025-06-12 08:30 | 16.69 |
| 3115084_ | 2025-06-16 18:00 | 16.63 |
| 3115084_ | 2025-06-20 13:45 | 16.79 |
| 3115084_ | 2025-06-24 06:45 | 14.51 |
| 3115084_ | 2025-06-24 16:00 | 16.9 |
| 3115084_ | 2025-06-26 07:45 | 14.55 |
| 3115084_ | 2026-01-04 21:00 | 15.98 |
| 3115084_ | 2026-01-05 03:45 | 15.95 |
| 3115084_ | 2026-01-30 07:15 | 15.8 |
| 3115084_ | 2026-04-26 23:45 | 15.81 |

</details>

### `wl_unresponsive`: 12644 readings, 9 stations

river level within 1.5 cm for >= 3 h while rain at the gauges within 10 km totals >= 30 mm over the same window (largest rolling sum over those gauges). Flagged from the first reading where both hold until the level moves again; a flat level alone is base flow and is kept.

| graph_id | name | count | min_value | max_value | first | last |
| --- | --- | --- | --- | --- | --- | --- |
| 26558 | Kg. Perepat, Kapar | 10481 | -0.79 | 0.37 | 2024-08-05 16:45 | 2026-10-11 05:30 |
| 3017107_ | Seri Kembangan | 1625 | 36.4 | 36.76 | 2024-04-13 02:30 | 2025-06-20 08:00 |
| PEKANMERU | Pekan Meru | 337 | 2.8 | 3.08 | 2024-05-08 19:30 | 2026-09-30 16:15 |
| 3015089_ | Tugu Keris | 93 | 2.06 | 2.18 | 2024-04-18 21:15 | 2026-04-20 20:30 |
| 3115084_ | Kg. Melayu Subang | 69 | 13.88 | 14.66 | 2025-01-04 14:45 | 2026-05-05 15:15 |
| 3015083_ | TTDI Jaya | 31 | 3.61 | 3.63 | 2026-01-03 20:30 | 2026-04-08 03:00 |
| 3115083_ | Taman Mayang | 5 | 14.11 | 14.13 | 2026-09-09 16:15 | 2026-09-17 16:45 |
| 3016080_ | Kg. Gandhi | 2 | 10.43 | 10.44 | 2026-09-25 16:45 | 2026-09-25 17:00 |
| DESAKEMUNING | Taman Desa Kemuning | 1 | 1.23 | 1.23 | 2025-11-11 08:30 | 2025-11-11 08:30 |

12644 readings: too many to list; section 3a shows the runs.

## 3. False-positive checks (do real storms survive?)

**Largest rain values kept** (all below the 100 mm limit; 32 readings >= 60 mm remain):

| graph_id | time_local | rain_15min_mm |
| --- | --- | --- |
| 26405 | 2024-05-01 16:00 | 100.0 |
| 26405 | 2024-05-08 19:30 | 100.0 |
| 26405 | 2024-05-23 17:00 | 95.0 |
| 27399 | 2026-10-01 16:00 | 95.0 |
| 26425 | 2024-06-28 15:15 | 87.0 |
| 27397 | 2026-09-26 15:00 | 86.5 |
| 26405 | 2024-05-07 14:45 | 85.0 |
| TELOKGONG | 2026-03-18 18:45 | 80.5 |
| TELOKGONG | 2026-04-03 17:30 | 80.5 |
| 27896 | 2026-09-29 21:00 | 77.0 |

**Smallest positive rain values removed**: 25 mm (removed by `rain_stuck`; `rain_after_gap` removed 7 readings, `rain_counter_rebound` 2; all listed in section 2).

**`rain_after_gap` candidates spared because the storm continued** (1): a catch-up is a single lump followed by silence; these are followed by a different reading of >= 10 mm (or are a gauge's latest reading), so they look like a storm that began during the gap.

| graph_id | time_local | rain_15min_mm | next_reading_mm |
| --- | --- | --- | --- |
| 27233 | 2025-03-06 00:00 | 30.5 | 24.0 |

**`rain_stuck`** removed 6 readings that no earlier rule had caught. Repeated implausible values (already removed by `rain_implausible`): 26502 repeats 893.5 mm 5 times; 26507 repeats 365.5 mm 3 times; 27879 repeats 287.5 mm 23 times; 27879 repeats 296.5 mm 7 times. The stuck rule is a guard for a gauge that sticks below the implausible limit.

**12 Nov 2024, 06:00-12:00:** 23 readings flagged at any station (26558, rule wl_unresponsive). PEKANMERU river level and the rain gauges within 10 km are unchanged (regression test `tests/test_qc.py::test_12_nov_2024_storm_is_untouched`, and section 3a).

**`wl_spike`**: 132 readings at 9 stations; the most are {'3115080_': 75, '3115084_': 25, '3115083_': 9}. Flagged values range from -6.58 m to 37.65 m. 7 flagged values are negative: each is a single-reading plunge below its neighbours, not a tidal swing. 13 flagged reading(s) sit directly next to another flagged reading (a burst of two or more bad readings, or a good reading between two spikes).

**`rain_counter_rebound`**: 2 readings removed after a counter dip, largest 56.5 mm.

## 3a. `wl_unresponsive`: evidence and false-positive risk

> **Pending regeneration.** The tables below were computed with the first version of the rule (3 h flat window, no response lag, no alert guard). The rule now needs 4.5 h flat with rain from the 3 h ending 90 min earlier and never flags a level at or above the alert level. Re-run `python scripts/qc_report.py` when the archive is rebuilt. On 26558 alone (own gauge): 8,307 flags in 20 runs, longest 2,986 readings.

**12 Nov 2024, 06:00-12:00:** Kg. Perepat (26558) read -0.79 m throughout while Pekan Meru rose; 23 readings of 26558 are flagged (from 06:00), 0 readings of PEKANMERU are flagged (regression test `tests/test_qc_unresponsive.py::test_12_nov_2024_26558_is_flagged_and_pekan_meru_is_not`).

**Flags per station** (runs = separate flat stretches; the three stations with most flags are examined below):

| graph_id | name | readings | first | last | runs | gauges_within_radius |
| --- | --- | --- | --- | --- | --- | --- |
| 26558 | Kg. Perepat, Kapar | 10481 | 2024-08-05 | 2026-10-11 | 177 | 4 |
| 3017107_ | Seri Kembangan | 1625 | 2024-04-13 | 2025-06-20 | 24 | 4 |
| PEKANMERU | Pekan Meru | 337 | 2024-05-08 | 2026-09-30 | 22 | 8 |
| 3015089_ | Tugu Keris | 93 | 2024-04-18 | 2026-04-20 | 8 | 14 |
| 3115084_ | Kg. Melayu Subang | 69 | 2025-01-04 | 2026-05-05 | 11 | 8 |
| 3015083_ | TTDI Jaya | 31 | 2026-01-03 | 2026-04-08 | 2 | 13 |
| 3115083_ | Taman Mayang | 5 | 2026-09-09 | 2026-09-17 | 2 | 14 |
| 3016080_ | Kg. Gandhi | 2 | 2026-09-25 | 2026-09-25 | 1 | 14 |
| DESAKEMUNING | Taman Desa Kemuning | 1 | 2025-11-11 | 2025-11-11 | 1 | 12 |

**26558 Kg. Perepat, Kapar** (level range -1.19 to 1.08 m); the 8 longest runs:

| run_start | readings | flat_level_m | rain_3h_at_start_mm | max_rain_3h_in_run_mm | first_level_after_run_m |
| --- | --- | --- | --- | --- | --- |
| 2024-10-31 01:30 | 733 | -0.78 | 43.0 | 72.5 | -0.78 |
| 2025-12-18 15:15 | 579 | 0.36 | 0.5 | 17.5 | 0.36 |
| 2026-01-05 19:00 | 561 | 0.36 | 0.0 | 19.5 | 0.36 |
| 2024-08-14 00:15 | 378 | -0.78 | 0.0 | 28.5 | -0.78 |
| 2026-06-18 14:30 | 377 | 0.36 | 0.0 | 16.0 | 0.34 |
| 2025-12-15 01:30 | 336 | 0.36 | 0.0 | 14.0 | 0.36 |
| 2026-01-11 15:30 | 327 | 0.36 | 0.0 | 23.5 | 0.34 |
| 2024-08-21 04:45 | 301 | -0.78 | 0.0 | 15.5 | -0.81 |

**3017107_ Seri Kembangan** (level range 34.71 to 38.65 m); the 8 longest runs:

| run_start | readings | flat_level_m | rain_3h_at_start_mm | max_rain_3h_in_run_mm | first_level_after_run_m |
| --- | --- | --- | --- | --- | --- |
| 2024-05-20 13:30 | 906 | 36.54 | 32.0 | 58.0 |  |
| 2024-06-17 15:00 | 241 | 36.55 | 37.5 | 56.5 | 36.57 |
| 2024-06-04 15:00 | 152 | 36.54 | 31.0 | 38.5 | 36.56 |
| 2024-04-17 07:45 | 94 | 36.41 | 63.5 | 67.0 | 36.48 |
| 2024-10-28 14:45 | 66 | 36.55 | 31.0 | 35.0 | 36.57 |
| 2024-05-11 19:00 | 38 | 36.53 | 34.0 | 34.0 | 36.55 |
| 2024-08-22 19:00 | 35 | 36.54 | 53.5 | 53.5 | 36.56 |
| 2024-08-07 17:15 | 24 | 36.55 | 34.5 | 34.5 | 36.57 |

**PEKANMERU Pekan Meru** (level range 2.69 to 4.76 m); the 8 longest runs:

| run_start | readings | flat_level_m | rain_3h_at_start_mm | max_rain_3h_in_run_mm | first_level_after_run_m |
| --- | --- | --- | --- | --- | --- |
| 2024-06-10 15:30 | 113 | 2.83 | 31.0 | 37.0 | 2.85 |
| 2026-09-09 07:30 | 72 | 2.93 | 30.5 | 30.5 | 2.92 |
| 2026-01-03 19:00 | 28 | 3.07 | 44.5 | 45.0 | 3.05 |
| 2026-04-09 06:15 | 18 | 2.9 | 33.5 | 37.0 | 2.89 |
| 2025-02-26 20:45 | 17 | 2.96 | 31.5 | 61.5 | 2.96 |
| 2024-05-08 19:30 | 16 | 2.9 | 31.0 | 39.0 | 2.92 |
| 2025-02-27 01:15 | 15 | 2.96 | 0.5 | 0.5 | 2.94 |
| 2026-04-26 10:30 | 14 | 2.92 | 0.0 | 0.0 | 2.9 |

**Tidal stations**: a tidal level swings with the 12.4 h tide, so its level at lag 25 (6.25 h) is anti-correlated with now. 2 of 15 river stations have lag-25 autocorrelation < -0.2 (3014080_, PANDAMARAN); 0 of their readings are flagged. No exclusion is needed.

| graph_id | name | lag25_autocorr | flagged_readings |
| --- | --- | --- | --- |
| 3014080_ | Bandar Klang | -0.74 | 0 |
| PANDAMARAN | P/A Pandamaran | -0.26 | 0 |
| DESAKEMUNING | Taman Desa Kemuning | 0.18 | 1 |
| 3015084_ | Taman Sri Muda | 0.19 | 0 |
| 3015001_ | Puchong Drop | 0.32 | 0 |

**False-positive risks** (read the run tables above):

- A river that is mostly base flow and drains a large or slow catchment can stay within 1.5 cm for 3 h of heavy rain at one nearby gauge (the rule takes the largest of the gauges within the radius, so a rain cell over one gauge counts). Pekan Meru shows this: its flags sit at base-flow levels and the level after the run is within a few cm.
- A run lasts until the level moves, so it continues after the rain stops. A genuinely flat river is kept NaN until it moves.
- A station whose gauge really is stuck for days or weeks is flagged for all of it once heavy rain has occurred, which is intended. A flag makes the value NaN: the rule engine forward-fills a level for 2 h, so staleness starts after that, and confidence is low only when no township station reports; ML features lose the readings at once. A wrong flag can hide a rising river, hence the alert-level guard and the 90 min lag.

## 4. Completeness and gaps per station (after QC)

`valid_%` = non-missing readings between the station's first and last valid reading, out of the 15-min slots in that span. `longest_gap_h` = longest stretch between two valid readings.

### River level (WL)

| graph_id | name | first | last | valid_% | longest_gap_h | gap_start |
| --- | --- | --- | --- | --- | --- | --- |
| 26039 | Kg. Budiman | 2024-04-01 | 2026-10-16 | 58.6 | 7924.0 | 2024-11-26 10:45 |
| 26558 | Kg. Perepat, Kapar | 2024-04-01 | 2026-10-16 | 81.3 | 775.2 | 2025-12-13 18:00 |
| 3014080_ | Bandar Klang | 2024-04-01 | 2026-10-16 | 87.4 | 1097.2 | 2026-04-02 20:30 |
| 3015001_ | Puchong Drop | 2024-04-01 | 2026-10-16 | 86.7 | 1726.0 | 2026-08-03 14:30 |
| 3015083_ | TTDI Jaya | 2024-04-01 | 2026-10-16 | 94.0 | 452.5 | 2025-03-29 15:15 |
| 3015084_ | Taman Sri Muda | 2024-04-01 | 2026-10-16 | 84.3 | 1273.5 | 2024-07-02 14:45 |
| 3015089_ | Tugu Keris | 2024-04-01 | 2026-10-16 | 94.2 | 452.5 | 2025-03-29 15:15 |
| 3016080_ | Kg. Gandhi | 2024-04-01 | 2026-10-16 | 62.5 | 7762.2 | 2024-10-06 01:30 |
| 3017107_ | Seri Kembangan | 2024-04-01 | 2026-10-16 | 85.9 | 452.8 | 2025-03-29 15:15 |
| 3115080_ | Paya Jaras | 2024-04-01 | 2026-10-16 | 42.4 | 11404.2 | 2024-07-09 11:30 |
| 3115083_ | Taman Mayang | 2024-04-01 | 2026-10-16 | 45.3 | 10560.5 | 2024-08-13 15:15 |
| 3115084_ | Kg. Melayu Subang | 2024-04-01 | 2026-10-16 | 78.6 | 815.2 | 2025-02-08 15:45 |
| DESAKEMUNING | Taman Desa Kemuning | 2024-04-01 | 2026-10-16 | 91.3 | 939.8 | 2025-03-29 15:15 |
| PANDAMARAN | P/A Pandamaran | 2024-04-01 | 2026-10-16 | 93.4 | 452.8 | 2025-03-29 15:15 |
| PEKANMERU | Pekan Meru | 2024-04-01 | 2026-10-16 | 93.6 | 402.2 | 2025-03-29 15:15 |

### Rain (RF)

| graph_id | name | first | last | valid_% | longest_gap_h | gap_start |
| --- | --- | --- | --- | --- | --- | --- |
| 2414401_ | SMK Jalan Kebun | 2024-01-01 | 2026-10-16 | 96.8 | 448.0 | 2025-03-29 15:00 |
| 26038 | Taman Sentosa | 2024-01-01 | 2026-10-16 | 83.0 | 3292.8 | 2026-04-23 10:30 |
| 26039 | Kg. Budiman | 2024-01-01 | 2026-10-16 | 92.0 | 448.0 | 2025-03-29 15:00 |
| 26350 | Jalan Ang Seng (F2) | 2024-01-01 | 2026-10-16 | 83.7 | 1893.0 | 2025-09-06 10:15 |
| 26352 | Sri Rampai (F2) | 2024-01-01 | 2026-10-15 | 76.7 | 965.5 | 2025-12-08 07:15 |
| 26353 | LRT Bukit Jalil (F2) | 2024-01-01 | 2026-10-16 | 78.7 | 734.0 | 2026-06-15 17:00 |
| 26371 | Sek. Men. Aminuddin Baki (F2) | 2024-01-01 | 2026-10-16 | 84.6 | 887.8 | 2024-02-22 09:30 |
| 26377 | Sentul Park (F2) | 2024-01-01 | 2026-10-16 | 80.9 | 908.5 | 2024-03-23 17:15 |
| 26382 | Razak Mansion (F2) | 2024-01-01 | 2026-10-16 | 73.4 | 1831.8 | 2025-09-03 09:15 |
| 26384 | Universiti Malaya (F2) | 2024-01-01 | 2026-10-16 | 85.3 | 1003.0 | 2025-09-11 10:45 |
| 26385 | Sek. Men. Keb. Wangsa Maju Seksyen 2 (F2) | 2024-03-29 | 2026-10-16 | 86.1 | 867.2 | 2024-04-01 23:00 |
| 26388 | Taman Shamelin Perkasa (F2) | 2024-01-01 | 2026-10-16 | 92.1 | 602.5 | 2025-09-07 01:00 |
| 26393 | Segambut Bahagia TNB (F2) | 2024-01-01 | 2026-10-16 | 86.8 | 909.5 | 2024-02-10 13:30 |
| 26396 | Segambut Dalam (F2) | 2024-01-01 | 2026-10-16 | 90.6 | 564.8 | 2026-06-22 04:00 |
| 26403 | Kg. Padang Balang (F2) | 2024-01-01 | 2026-10-16 | 88.5 | 446.2 | 2025-03-29 15:00 |
| 26405 | Taman Damai Murni (F2) | 2024-01-01 | 2026-10-16 | 70.5 | 2441.5 | 2024-01-18 21:15 |
| 26410 | Jalan Pasir Rendah (F2) | 2024-01-04 | 2026-10-16 | 75.6 | 1508.8 | 2026-05-14 13:45 |
| 26413 | Bukit Putra (F2) | 2024-01-01 | 2026-10-16 | 75.9 | 1096.0 | 2025-09-07 13:45 |
| 26414 | Kolam Takungan Banjir Sg. Midah (F2) | 2024-01-01 | 2026-10-16 | 87.7 | 991.0 | 2025-12-02 08:00 |
| 26415 | Lebuhraya KL-Seremban (F2) | 2024-06-12 | 2026-10-16 | 70.4 | 2348.2 | 2026-04-15 16:00 |
| 26416 | Bangunan Bahagian Teknologi Pendidikan (F2) | 2024-01-01 | 2026-10-16 | 93.3 | 486.5 | 2024-06-27 03:30 |
| 26420 | Kg. Muda (F2) | 2024-01-01 | 2026-10-16 | 79.8 | 2910.2 | 2024-01-03 06:00 |
| 26421 | Taman Sri Kuching (F2) | 2024-04-05 | 2026-10-16 | 75.2 | 960.0 | 2025-10-26 16:15 |
| 26424 | Komuter Segambut (F2) | 2024-02-20 | 2026-10-16 | 83.4 | 1866.8 | 2025-08-22 18:30 |
| 26425 | Sek. Men. Agama Kuala Lumpur Bandar Manjalara (F2) | 2024-04-29 | 2026-10-16 | 89.1 | 477.8 | 2024-05-24 12:45 |
| 26497 | Kg. Berembang (SMART) | 2024-01-05 | 2026-10-16 | 85.4 | 2923.5 | 2024-08-08 17:00 |
| 26502 | JPS Wilayah (F2) | 2024-01-01 | 2026-10-16 | 67.4 | 3249.5 | 2026-03-02 02:45 |
| 26506 | Kg. Cheras Baru (F2) | 2024-01-01 | 2026-10-16 | 61.9 | 2431.0 | 2026-03-15 02:30 |
| 26507 | Empangan Batu (F2) | 2024-01-01 | 2025-08-25 | 85.8 | 459.5 | 2024-07-06 11:00 |
| 26558 | Kg. Perepat, Kapar | 2024-01-01 | 2026-10-16 | 96.1 | 448.0 | 2025-03-29 15:00 |
| 27232 | Sri Manja | 2024-01-05 | 2026-10-16 | 90.0 | 448.0 | 2025-03-29 15:00 |
| 27233 | Kg. Lombong | 2024-01-05 | 2026-10-16 | 89.1 | 448.0 | 2025-03-29 15:00 |
| 27234 | P/A Kg. Sg. Kandis | 2024-01-05 | 2026-10-16 | 87.4 | 2192.5 | 2025-08-08 10:30 |
| 27394 |  | 2024-05-24 | 2026-10-16 | 59.4 | 1612.2 | 2026-04-10 13:00 |
| 27395 | SMK SS 17 (F2) | 2024-05-24 | 2026-10-14 | 51.8 | 716.5 | 2026-04-28 23:45 |
| 27397 | KDR Sandaran Permai (F2) | 2024-05-24 | 2026-10-16 | 62.8 | 2080.2 | 2024-06-15 22:45 |
| 27399 | Jave Setia (F2) | 2024-06-04 | 2026-10-16 | 80.7 | 2004.5 | 2024-06-20 22:30 |
| 27400 | Ayer Hitam Puchong (F2) | 2024-06-04 | 2026-10-16 | 64.0 | 3614.2 | 2024-09-26 23:00 |
| 27401 | Surau Al-Syakirin (F2) | 2024-06-05 | 2026-10-16 | 76.1 | 1026.8 | 2024-07-02 23:00 |
| 27859 | Emp. Tasik Subang Meru (F2) | 2025-11-17 | 2026-10-16 | 84.6 | 577.5 | 2026-03-03 15:45 |
| 27865 | SG. DAMANSARA di KG MELAYU KEBUN BUNGA (F2) | 2025-11-06 | 2026-10-16 | 99.2 | 53.2 | 2026-08-18 10:30 |
| 27874 | Taman Kayu Ara Indah (F2) | 2025-11-06 | 2026-10-16 | 99.3 | 53.2 | 2026-08-18 10:30 |
| 27875 | Sungai Klang di LDP (F2) | 2025-11-14 | 2026-10-16 | 62.9 | 1367.0 | 2026-01-29 17:30 |
| 27877 | USJ 1 (F2) | 2025-12-29 | 2026-10-16 | 99.1 | 53.2 | 2026-08-18 10:30 |
| 27879 | Jalan SS 2/24 (F2) | 2025-11-06 | 2026-10-16 | 87.2 | 61.5 | 2026-05-30 05:00 |
| 27880 | Rem KTM Sungai Buloh  (F2) | 2025-09-28 | 2026-10-16 | 60.2 | 2319.5 | 2026-05-13 16:30 |
| 27896 | Taman Mayang (F2) | 2025-02-24 | 2026-10-16 | 84.6 | 448.0 | 2025-03-29 15:00 |
| 27900 | Kg. Gandhi (F2) | 2025-01-16 | 2026-10-16 | 93.6 | 448.0 | 2025-03-29 15:00 |
| 27901 | Jalan 222 (F2) | 2025-01-16 | 2026-10-16 | 65.6 | 2533.8 | 2025-07-10 19:00 |
| 27928 | Bandar Klang (F2) | 2025-02-03 | 2026-10-16 | 93.4 | 447.8 | 2025-03-29 15:00 |
| 27946 | Kg. Delek (F2) | 2025-11-05 | 2026-10-16 | 99.3 | 53.2 | 2026-08-18 10:30 |
| 27948 | SK Bukit Kemuning (F2) | 2025-11-06 | 2026-10-16 | 96.7 | 168.5 | 2026-03-05 15:15 |
| 28043 | Sg. Rasau AJ (F2) | 2025-01-22 | 2026-10-16 | 89.4 | 509.2 | 2026-03-23 07:45 |
| 28044 | Batu 3 (F2) | 2025-01-16 | 2026-10-16 | 82.6 | 912.2 | 2026-08-18 10:30 |
| 28397 | Pandamar (F2) | 2025-11-06 | 2026-10-16 | 99.3 | 53.2 | 2026-08-18 10:30 |
| 28425 | Bukit Jelutong (F2) | 2025-11-07 | 2026-10-16 | 94.3 | 323.2 | 2026-02-10 23:00 |
| 28426 | Sg. Renggam Bung Hurris (F2) | 2025-11-06 | 2026-10-16 | 87.4 | 512.0 | 2026-03-06 09:15 |
| 28427 | Kg. Merbau Sempak (F2) | 2026-01-22 | 2026-10-16 | 49.4 | 285.5 | 2026-01-22 15:00 |
| 28428 | Bukit Lancong FAZ (F2) | 2025-11-14 | 2026-10-16 | 95.3 | 306.8 | 2026-03-05 15:00 |
| 28431 | Taman Sri Manja (F2) | 2025-12-29 | 2026-10-16 | 99.1 | 53.2 | 2026-08-18 10:30 |
| 2915118_ | Ayer Hitam Puchong | 2024-01-01 | 2026-10-16 | 89.9 | 448.0 | 2025-03-29 15:00 |
| 3014080_ | Bandar Klang | 2024-01-01 | 2026-10-16 | 91.5 | 1097.5 | 2026-04-02 20:30 |
| 3015001_ | Puchong Drop | 2024-01-01 | 2026-10-16 | 96.2 | 448.2 | 2025-03-29 14:45 |
| 3015083_ | TTDI Jaya | 2024-01-01 | 2026-10-16 | 97.0 | 448.2 | 2025-03-29 14:45 |
| 3015084_ | Taman Sri Muda | 2024-01-01 | 2026-10-16 | 96.3 | 448.2 | 2025-03-29 14:45 |
| 3015087_ | Batu 3 | 2024-01-01 | 2026-10-16 | 96.7 | 448.0 | 2025-03-29 15:00 |
| 3015089_ | Tugu Keris | 2024-01-01 | 2026-10-16 | 96.3 | 448.2 | 2025-03-29 14:45 |
| 3015440_ | IOI Puchong Jaya | 2024-01-01 | 2026-10-16 | 92.8 | 448.0 | 2025-03-29 15:00 |
| 3016002_ | Jambatan Petaling | 2024-01-01 | 2026-10-16 | 78.3 | 446.2 | 2025-03-29 15:00 |
| 3016077_ | Jalan 222 | 2024-01-01 | 2026-10-16 | 89.9 | 1664.8 | 2025-08-30 04:30 |
| 3016080_ | Kg. Gandhi | 2024-01-01 | 2026-10-16 | 96.7 | 448.0 | 2025-03-29 15:00 |
| 3017107_ | Seri Kembangan | 2024-01-01 | 2026-10-16 | 91.0 | 448.0 | 2025-03-29 15:00 |
| 3114005_ | Lembah Keramat | 2024-01-01 | 2026-10-16 | 97.3 | 446.2 | 2025-03-29 15:00 |
| 3114087_ | Empangan Tasik Subang Meru | 2024-01-01 | 2026-10-16 | 95.2 | 448.2 | 2025-03-29 14:45 |
| 3115080_ | Paya Jaras | 2024-01-01 | 2026-10-16 | 93.4 | 448.0 | 2025-03-29 15:00 |
| 3115083_ | Taman Mayang | 2024-01-01 | 2026-10-16 | 96.0 | 448.0 | 2025-03-29 15:00 |
| 3115084_ | Kg. Melayu Subang | 2024-01-01 | 2026-10-16 | 88.8 | 448.5 | 2025-03-29 15:00 |
| 3116004_ | JPS Wilayah | 2024-01-01 | 2026-10-16 | 97.1 | 446.2 | 2025-03-29 15:00 |
| 3116006_ | Ladang Edinburgh | 2024-01-01 | 2026-10-16 | 94.1 | 446.2 | 2025-03-29 15:00 |
| 3116074_ | Leboh Pasar | 2024-01-01 | 2026-10-16 | 94.3 | 446.2 | 2025-03-29 15:00 |
| 3117005_ | Kg. Air Panas | 2024-01-01 | 2026-10-16 | 7.7 | 10844.5 | 2025-05-23 11:30 |
| 3117006_ | Kolam Takungan Batu | 2024-01-01 | 2026-09-17 | 94.6 | 446.2 | 2025-03-29 15:00 |
| 3117070_ | JPS Ampang | 2024-01-01 | 2026-10-16 | 75.7 | 1418.0 | 2024-06-16 10:30 |
| 3117403_ | Jln. Tun Razak (Sg. Bunus) | 2024-01-01 | 2026-10-16 | 97.3 | 446.2 | 2025-03-29 15:00 |
| 3216007_ | Taman Ehsan | 2024-08-22 | 2026-10-16 | 86.4 | 446.2 | 2025-03-29 15:00 |
| BTU10_ | Kg. Batu Muda (F2) | 2024-01-01 | 2026-10-16 | 80.5 | 1558.8 | 2026-05-06 13:15 |
| DESAKEMUNING | Taman Desa Kemuning | 2024-01-01 | 2026-10-16 | 96.4 | 448.0 | 2025-03-29 15:00 |
| JLNBENTENGKAPAR | Jln. Benteng Kapar | 2024-01-01 | 2026-10-16 | 93.3 | 448.0 | 2025-03-29 15:00 |
| KGDELEK | Kg. Delek | 2024-01-01 | 2026-10-16 | 66.7 | 4318.2 | 2024-11-23 07:00 |
| KGRANTAUPANJANG | Kg. Rantau Panjang | 2024-01-01 | 2026-10-16 | 95.8 | 448.0 | 2025-03-29 15:00 |
| KOTADAMANSARA | Kota Damansara | 2024-01-01 | 2026-10-16 | 94.1 | 448.2 | 2025-03-29 14:45 |
| LDGELMINA | Ladang Elmina | 2024-01-01 | 2026-10-16 | 93.8 | 479.2 | 2024-02-08 12:45 |
| PANDAMARAN | P/A Pandamaran | 2024-01-01 | 2026-10-16 | 96.6 | 448.0 | 2025-03-29 15:00 |
| PEKANMERU | Pekan Meru | 2024-01-01 | 2026-10-16 | 96.6 | 402.5 | 2025-03-29 15:00 |
| SELATMUARA | Selat Muara | 2024-01-01 | 2026-10-16 | 96.1 | 448.2 | 2025-03-29 14:45 |
| SMKRAJALUMU | SMK Raja Lumu | 2024-01-01 | 2026-10-16 | 89.7 | 588.2 | 2024-08-24 02:45 |
| SURAUALSYAKIRIN | Surau Al-Syakirin | 2025-05-22 | 2026-10-16 | 9.9 | 10614.0 | 2025-05-23 11:30 |
| TAMANBOTANI | Taman Botani | 2024-01-01 | 2026-10-16 | 96.5 | 448.2 | 2025-03-29 14:45 |
| TELOKGONG | Telok Gong | 2024-01-01 | 2026-10-16 | 94.2 | 448.2 | 2025-03-29 14:45 |
| USJ1 | USJ 1 | 2024-01-01 | 2026-10-16 | 91.2 | 646.2 | 2025-02-01 16:45 |

## 5. Tide gaps and the harmonic fill

Open-Meteo Marine (cached in `data/raw/tide/`) covers 2024-01-01 to 2026-10-19; 432 hours have no value.

| from | to | hours |
| --- | --- | --- |
| 2024-06-12 08:00 | 2024-06-19 07:00 | 168 |
| 2025-01-29 08:00 | 2025-02-09 07:00 | 264 |

Missing hours are filled with a least-squares harmonic fit (mean + M2, S2, N2, K2, K1, O1, P1, Q1, M4, MS4, Sa, Ssa) to the 24120 observed hours and marked `tide_filled`. Observed hours are never changed.

High-water times (`hours_to_high_tide`) now come from the fit evaluated every 5 min and shifted +40 min later, because Open-Meteo's highs are early against independent data (UHSLC Port Kelang gauge median -35 min, official forecasts -48 min, tide-forecast.com -38 min; see `docs/tide-check.md`). `tide_height_m` is unchanged (not shifted, not rescaled).

**Before / after** (`hours_to_high_tide`):

|  | max_abs_h | NaN_tide_height |
| --- | --- | --- |
| before (no fill) | 137.0 | 432 |
| after (harmonic fill) | 7.0 | 0 |

After the fix `hours_to_high_tide` is NaN on 5 hour(s) (2024-03-19 07:00, 2024-04-17 06:00, 2024-04-17 07:00, 2025-09-02 19:00, 2026-09-21 07:00): the fit has no high water within 7 h of them (a weak neap-tide hump), and NaN is reported instead of a far-away high. Never beyond +-7 h.

**Hold-out validation**: fit without a 10-day window that has data, then compare the fit with the series there. Timing error = predicted minus observed high-water time (hourly data, so a resolution of 1 h).

| window | RMSE_m | bias_m | series_std_m | highs_matched | mean_abs_timing_h | max_abs_timing_h |
| --- | --- | --- | --- | --- | --- | --- |
| 2024-03-10 + 10 d | 0.128 | 0.039 | 1.168 | 19/19 | 0.26 | 1.0 |
| 2024-08-20 + 10 d | 0.094 | 0.004 | 1.107 | 19/19 | 0.26 | 1.0 |
| 2024-11-05 + 10 d | 0.108 | 0.013 | 0.876 | 19/19 | 0.32 | 1.0 |
| 2025-04-15 + 10 d | 0.12 | -0.038 | 0.845 | 19/19 | 0.37 | 1.0 |
| 2025-08-10 + 10 d | 0.198 | -0.178 | 1.042 | 19/19 | 0.0 | 0.0 |
| 2026-02-01 + 10 d | 0.086 | 0.03 | 1.096 | 20/20 | 0.05 | 1.0 |

Mean over windows: RMSE 0.122 m (the series itself varies by 1.02 m std), mean absolute high-water timing error 0.21 h.

The fit reproduces the astronomical tide; it cannot reproduce weather surge, so filled hours carry an error of about the RMSE above. This matters only for the 432 filled hours (1.8%), which are flagged in `tide_filled`.
