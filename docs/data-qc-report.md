# Data QC report

Generated 16 Oct 2026 by `scripts/qc_report.py` on the JPS history archive as it stands today: 50 rain gauges and 15 river stations, 5,694,288 15-min rows, 2024-01-01 to 2026-10-16 (archive progress 16/312 station series). **The archive is still being filled; this report will be regenerated when it finishes** (`python scripts/qc_report.py`).

Rules live in `floodready/qc.py` and run inside `engine/replay.py::load_archive_readings` and `live.py::load_live_readings`, so replay, training, the API and live data all see the cleaned values. A flagged value becomes NaN, never 0.

**Live mode:** `wl_spike` and `rain_after_gap` need the next reading. A gauge's latest reading is kept and judged when the next one arrives, so a real rise or storm after an outage is never hidden. Archive cleaning (replay, training) sees the reading at t+15 min, live cleaning does not: a small train/serve difference, limited to the latest reading of each gauge.

## 1. Summary

| rule | readings | stations | rule_text |
| --- | --- | --- | --- |
| rain_negative | 28 | 28 | rain < 0 (a counter cannot go down: 1 Jan reset, gauge restart) |
| rain_implausible | 60 | 23 | rain > 100 mm per 15 min (> 400 mm/h) |
| rain_counter_rebound | 1 | 1 | a positive reading within 24 h after a dip of <= -5 mm at the same gauge, equal to the dip within max(1 mm, 5 %): the counter dipped and was restored |
| rain_after_gap | 3 | 2 | rain >= 30 mm in the first reading after >= 2 h without readings, unless the next reading is >= 10 mm and different (a storm that continues); an identical repeat right after is removed too. A gauge's latest reading is kept until the next arrives |
| rain_stuck | 0 | 0 | the same value >= 20 mm at least 3 times within 24 h at one gauge (only readings not already removed by the rules above) |
| wl_spike | 132 | 9 | river level more than 1 m from both neighbours in the same direction, with the neighbours within max(0.2 m, half the jump) of each other. A station's latest reading is kept until the next arrives |
| wl_unresponsive | 10302 | 4 | river level within 1.5 cm for 4.5 h (3 h rain window + the fixed 90 min response lag) while at least 2 rain gauges within 10 km each total >= 30 mm over the 3 h that ended 90 min before the reading (the second-wettest gauge decides, so one local rain cell is not enough). Flagged from the first reading where both hold until the level moves out of its band; a run resumes if the level is back in the band within 4 readings; a flat level alone is base flow and is kept. Dead-gauge state: 2 storms (the nearest gauge and the second-wettest gauge both >= 30 mm in 3 h, >= 48 h apart, within 30 days) with no response (range < 0.1 m within 8 h) while a river station within 15 km rose >= 0.3 m make the gauge dead: every reading below alert is flagged until it rises or falls >= 0.2 m within 8 h (3-reading median, so a revived gauge leaves one reading late); after it ends one more unanswered storm within 30 days puts it back; tidal neighbours never count as corroboration (excluded rather than de-tided: differencing changed no flag). Nothing at or above the alert level is ever flagged. The nearest-gauge condition, the 48 h separation and the median were added after looking at the archive (see section 3a). Not flagged (no evidence): stations with fewer than 2 gauges in range (a gauge stuck low there is not caught) or untrusted/missing thresholds |
| rain_monthly_implausible | (not in this run; counts at the next regeneration) | | rolling 30-day rain total > 600 mm and > 3x the median total of the gauges within 10 km (at least 2 neighbours, each with data in 80% of the window; a gappy neighbour is left out, never counted as dry), and the same test on the last 7 days. Causal: readings > 0 are flagged from the moment both totals pass the test until the 7-day total is normal again. A gauge with no coordinates in the lookup (the DBKL (F2) gauges, 26405 among them) is compared with its district instead, where the district's gauges with coordinates span <= 25 km. Floor and ratio were fixed before looking at 12 Nov 2024; on the partial archive (which does not yet hold 26405) no healthy gauge is flagged, the wettest 30-day totals being about 750 mm |

92 of 3,999,611 rain readings (0.0023%) and 10434 river readings removed.

Thresholds: the largest rain value kept is 80.5 mm per 15 min; the values removed by `rain_implausible` range from 123.5 to 3169 mm. `rain_after_gap` needs the continuation test (section 3): without it it removed readings of storms that began during a gap.

## 2. Flagged readings by rule and station

### `rain_negative`: 28 readings, 28 stations

rain < 0 (a counter cannot go down: 1 Jan reset, gauge restart).

| graph_id | name | count | min_value | max_value | first | last |
| --- | --- | --- | --- | --- | --- | --- |
| 2414401_ | SMK Jalan Kebun | 1 | -2484.0 | -2484.0 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 26038 | Taman Sentosa | 1 | -2500.5 | -2500.5 | 2024-01-01 00:45 | 2024-01-01 00:45 |
| 26039 | Kg. Budiman | 1 | -1979.5 | -1979.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 26509 | Kg. Sg. Tua Empangan Batu (F2) | 1 | -32.5 | -32.5 | 2025-01-06 14:00 | 2025-01-06 14:00 |
| 26513 | Sentul (F2) | 1 | -317.5 | -317.5 | 2025-02-14 10:15 | 2025-02-14 10:15 |
| 2915118_ | Ayer Hitam Puchong | 1 | -2629.5 | -2629.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3014080_ | Bandar Klang | 1 | -2281.0 | -2281.0 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3015001_ | Puchong Drop | 1 | -2603.5 | -2603.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3015083_ | TTDI Jaya | 1 | -2336.5 | -2336.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3015084_ | Taman Sri Muda | 1 | -2320.5 | -2320.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3015089_ | Tugu Keris | 1 | -2497.5 | -2497.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3016080_ | Kg. Gandhi | 1 | -3274.5 | -3274.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3017107_ | Seri Kembangan | 1 | -2684.0 | -2684.0 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3114087_ | Empangan Tasik Subang Meru | 1 | -2444.0 | -2444.0 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3115080_ | Paya Jaras | 1 | -3115.5 | -3115.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3115083_ | Taman Mayang | 1 | -3131.5 | -3131.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3115084_ | Kg. Melayu Subang | 1 | -2639.5 | -2639.5 | 2024-01-01 00:15 | 2024-01-01 00:15 |
| 3116074_ | Leboh Pasar | 1 | -494.0 | -494.0 | 2024-08-09 16:15 | 2024-08-09 16:15 |
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
| 26509 | 2025-01-06 14:00 | -32.5 |
| 26513 | 2025-02-14 10:15 | -317.5 |
| 2915118_ | 2024-01-01 00:15 | -2629.5 |
| 3014080_ | 2024-01-01 00:15 | -2281.0 |
| 3015001_ | 2024-01-01 00:15 | -2603.5 |
| 3015083_ | 2024-01-01 00:15 | -2336.5 |
| 3015084_ | 2024-01-01 00:15 | -2320.5 |
| 3015089_ | 2024-01-01 00:15 | -2497.5 |
| 3016080_ | 2024-01-01 00:15 | -3274.5 |
| 3017107_ | 2024-01-01 00:15 | -2684.0 |
| 3114087_ | 2024-01-01 00:15 | -2444.0 |
| 3115080_ | 2024-01-01 00:15 | -3115.5 |
| 3115083_ | 2024-01-01 00:15 | -3131.5 |
| 3115084_ | 2024-01-01 00:15 | -2639.5 |
| 3116074_ | 2024-08-09 16:15 | -494.0 |
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

### `rain_implausible`: 60 readings, 23 stations

rain > 100 mm per 15 min (> 400 mm/h).

| graph_id | name | count | min_value | max_value | first | last |
| --- | --- | --- | --- | --- | --- | --- |
| 26513 | Sentul (F2) | 12 | 317.5 | 2635.0 | 2024-06-24 12:15 | 2025-02-14 11:30 |
| 26509 | Kg. Sg. Tua Empangan Batu (F2) | 7 | 123.5 | 2166.0 | 2024-06-26 17:15 | 2024-11-12 10:45 |
| 26512 | Ladang Edinburgh (F2) | 5 | 1534.5 | 1535.5 | 2024-08-09 13:00 | 2024-08-09 16:30 |
| 3017107_ | Seri Kembangan | 4 | 578.5 | 597.5 | 2026-05-01 12:45 | 2026-06-25 18:45 |
| 26511 | Empangan Klang (F2) | 3 | 449.0 | 926.0 | 2024-06-24 14:45 | 2024-08-09 14:15 |
| 2915118_ | Ayer Hitam Puchong | 3 | 230.0 | 436.0 | 2026-04-23 09:30 | 2026-06-25 17:15 |
| 3015440_ | IOI Puchong Jaya | 3 | 1895.5 | 2191.0 | 2025-11-21 01:00 | 2025-12-16 00:00 |
| 3115080_ | Paya Jaras | 3 | 1301.5 | 2185.0 | 2025-07-29 00:00 | 2025-12-25 00:00 |
| KOTADAMANSARA | Kota Damansara | 3 | 256.5 | 1388.0 | 2024-08-28 11:15 | 2024-09-11 16:15 |
| 3015084_ | Taman Sri Muda | 3 | 1756.5 | 2187.5 | 2025-10-17 00:00 | 2025-12-20 00:00 |
| TAMANBOTANI | Taman Botani | 2 | 2179.5 | 2364.5 | 2025-12-06 00:00 | 2025-12-20 00:00 |
| 26516 | Taman Cuepacs (F2) | 1 | 501.0 | 501.0 | 2024-07-02 13:00 | 2024-07-02 13:00 |
| 26514 | Lembah Jaya (F2) | 1 | 3169.0 | 3169.0 | 2025-12-29 14:30 | 2025-12-29 14:30 |
| 26039 | Kg. Budiman | 1 | 244.5 | 244.5 | 2024-02-14 20:30 | 2024-02-14 20:30 |
| 27233 | Kg. Lombong | 1 | 2569.5 | 2569.5 | 2025-12-20 03:00 | 2025-12-20 03:00 |
| 3016080_ | Kg. Gandhi | 1 | 1871.0 | 1871.0 | 2025-12-20 03:00 | 2025-12-20 03:00 |
| 3015083_ | TTDI Jaya | 1 | 1864.5 | 1864.5 | 2025-11-21 00:00 | 2025-11-21 00:00 |
| 3115083_ | Taman Mayang | 1 | 574.5 | 574.5 | 2026-04-23 12:00 | 2026-04-23 12:00 |
| 3116074_ | Leboh Pasar | 1 | 494.0 | 494.0 | 2024-08-09 16:30 | 2024-08-09 16:30 |
| KGRANTAUPANJANG | Kg. Rantau Panjang | 1 | 1693.0 | 1693.0 | 2025-11-21 00:00 | 2025-11-21 00:00 |
| KGDELEK | Kg. Delek | 1 | 1487.5 | 1487.5 | 2025-11-21 00:00 | 2025-11-21 00:00 |
| PANDAMARAN | P/A Pandamaran | 1 | 1697.0 | 1697.0 | 2025-12-17 00:00 | 2025-12-17 00:00 |
| USJ1 | USJ 1 | 1 | 1508.0 | 1508.0 | 2025-10-31 00:15 | 2025-10-31 00:15 |

<details><summary>Every flagged reading</summary>

| graph_id | time_local | value |
| --- | --- | --- |
| 26039 | 2024-02-14 20:30 | 244.5 |
| 26509 | 2024-06-26 17:15 | 1019.0 |
| 26509 | 2024-08-09 12:45 | 124.0 |
| 26509 | 2024-08-09 13:30 | 124.0 |
| 26509 | 2024-08-09 14:45 | 123.5 |
| 26509 | 2024-09-02 09:15 | 1508.5 |
| 26509 | 2024-10-01 00:15 | 1709.0 |
| 26509 | 2024-11-12 10:45 | 2166.0 |
| 26511 | 2024-06-24 14:45 | 449.0 |
| 26511 | 2024-08-09 13:00 | 926.0 |
| 26511 | 2024-08-09 14:15 | 926.0 |
| 26512 | 2024-08-09 13:00 | 1534.5 |
| 26512 | 2024-08-09 14:15 | 1534.5 |
| 26512 | 2024-08-09 15:15 | 1534.5 |
| 26512 | 2024-08-09 16:00 | 1535.5 |
| 26512 | 2024-08-09 16:30 | 1535.5 |
| 26513 | 2024-06-24 12:15 | 453.0 |
| 26513 | 2024-07-09 11:30 | 576.5 |
| 26513 | 2024-08-09 12:45 | 965.5 |
| 26513 | 2024-08-09 13:45 | 965.5 |
| 26513 | 2024-08-09 14:00 | 965.5 |
| 26513 | 2024-08-09 14:45 | 965.5 |
| 26513 | 2024-08-09 15:15 | 965.5 |
| 26513 | 2024-08-09 16:15 | 965.5 |
| 26513 | 2024-10-08 14:00 | 1317.5 |
| 26513 | 2024-10-22 13:15 | 2635.0 |
| 26513 | 2024-11-06 12:15 | 1322.0 |
| 26513 | 2025-02-14 11:30 | 317.5 |
| 26514 | 2025-12-29 14:30 | 3169.0 |
| 26516 | 2024-07-02 13:00 | 501.0 |
| 27233 | 2025-12-20 03:00 | 2569.5 |
| 2915118_ | 2026-04-23 09:30 | 230.0 |
| 2915118_ | 2026-05-05 09:00 | 230.0 |
| 2915118_ | 2026-06-25 17:15 | 436.0 |
| 3015083_ | 2025-11-21 00:00 | 1864.5 |
| 3015084_ | 2025-10-17 00:00 | 1756.5 |
| 3015084_ | 2025-11-21 09:00 | 1849.0 |
| 3015084_ | 2025-12-20 00:00 | 2187.5 |
| 3015440_ | 2025-11-21 01:00 | 1895.5 |
| 3015440_ | 2025-12-05 00:00 | 2191.0 |
| 3015440_ | 2025-12-16 00:00 | 2185.5 |
| 3016080_ | 2025-12-20 03:00 | 1871.0 |
| 3017107_ | 2026-05-01 12:45 | 578.5 |
| 3017107_ | 2026-05-08 20:00 | 597.5 |
| 3017107_ | 2026-06-21 21:15 | 587.0 |
| 3017107_ | 2026-06-25 18:45 | 589.5 |
| 3115080_ | 2025-07-29 00:00 | 1301.5 |
| 3115080_ | 2025-11-21 01:00 | 1796.5 |
| 3115080_ | 2025-12-25 00:00 | 2185.0 |
| 3115083_ | 2026-04-23 12:00 | 574.5 |
| 3116074_ | 2024-08-09 16:30 | 494.0 |
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

### `rain_counter_rebound`: 1 readings, 1 stations

a positive reading within 24 h after a dip of <= -5 mm at the same gauge, equal to the dip within max(1 mm, 5 %): the counter dipped and was restored.

| graph_id | name | count | min_value | max_value | first | last |
| --- | --- | --- | --- | --- | --- | --- |
| 26509 | Kg. Sg. Tua Empangan Batu (F2) | 1 | 32.5 | 32.5 | 2025-01-06 14:45 | 2025-01-06 14:45 |

<details><summary>Every flagged reading</summary>

| graph_id | time_local | value |
| --- | --- | --- |
| 26509 | 2025-01-06 14:45 | 32.5 |

</details>

### `rain_after_gap`: 3 readings, 2 stations

rain >= 30 mm in the first reading after >= 2 h without readings, unless the next reading is >= 10 mm and different (a storm that continues); an identical repeat right after is removed too. A gauge's latest reading is kept until the next arrives.

| graph_id | name | count | min_value | max_value | first | last |
| --- | --- | --- | --- | --- | --- | --- |
| 3115080_ | Paya Jaras | 2 | 61.0 | 61.0 | 2025-04-28 15:30 | 2025-04-28 15:45 |
| 3116074_ | Leboh Pasar | 1 | 38.0 | 38.0 | 2025-06-11 00:15 | 2025-06-11 00:15 |

<details><summary>Every flagged reading</summary>

| graph_id | time_local | value |
| --- | --- | --- |
| 3115080_ | 2025-04-28 15:30 | 61.0 |
| 3115080_ | 2025-04-28 15:45 | 61.0 |
| 3116074_ | 2025-06-11 00:15 | 38.0 |

</details>

### `rain_stuck`: 0 readings, 0 stations

the same value >= 20 mm at least 3 times within 24 h at one gauge (only readings not already removed by the rules above).

No readings flagged.

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

### `wl_unresponsive`: 10302 readings, 4 stations

river level within 1.5 cm for 4.5 h (3 h rain window + the fixed 90 min response lag) while at least 2 rain gauges within 10 km each total >= 30 mm over the 3 h that ended 90 min before the reading (the second-wettest gauge decides, so one local rain cell is not enough). Flagged from the first reading where both hold until the level moves out of its band; a run resumes if the level is back in the band within 4 readings; a flat level alone is base flow and is kept. Dead-gauge state: 2 storms (the nearest gauge and the second-wettest gauge both >= 30 mm in 3 h, >= 48 h apart, within 30 days) with no response (range < 0.1 m within 8 h) while a river station within 15 km rose >= 0.3 m make the gauge dead: every reading below alert is flagged until it rises or falls >= 0.2 m within 8 h (3-reading median, so a revived gauge leaves one reading late); after it ends one more unanswered storm within 30 days puts it back; tidal neighbours never count as corroboration (excluded rather than de-tided: differencing changed no flag). Nothing at or above the alert level is ever flagged. The nearest-gauge condition, the 48 h separation and the median were added after looking at the archive (see section 3a). Not flagged (no evidence): stations with fewer than 2 gauges in range (a gauge stuck low there is not caught) or untrusted/missing thresholds.

| graph_id | name | count | min_value | max_value | first | last |
| --- | --- | --- | --- | --- | --- | --- |
| 26558 | Kg. Perepat, Kapar | 9982 | -0.79 | 0.37 | 2024-08-05 18:15 | 2026-09-26 18:15 |
| PEKANMERU | Pekan Meru | 247 | 2.82 | 3.08 | 2024-05-08 21:00 | 2026-09-10 02:30 |
| 3015089_ | Tugu Keris | 52 | 2.16 | 2.17 | 2026-03-31 18:30 | 2026-04-20 20:45 |
| 3115084_ | Kg. Melayu Subang | 21 | 13.88 | 13.9 | 2025-01-04 16:15 | 2025-04-27 19:00 |

10302 readings: too many to list; section 3a shows the runs.

## 3. False-positive checks (do real storms survive?)

**Largest rain values kept** (all below the 100 mm limit; 10 readings >= 60 mm remain):

| graph_id | time_local | rain_15min_mm |
| --- | --- | --- |
| TELOKGONG | 2026-03-18 18:45 | 80.5 |
| TELOKGONG | 2026-04-03 17:30 | 80.5 |
| 3015440_ | 2025-12-19 18:30 | 77.0 |
| 3016077_ | 2026-05-06 16:00 | 76.0 |
| JLNBENTENGKAPAR | 2026-06-14 18:00 | 71.0 |
| 27234 | 2024-11-25 16:30 | 67.0 |
| 27234 | 2025-02-22 16:15 | 63.0 |
| 27928 | 2025-05-29 13:00 | 61.0 |
| 26039 | 2026-04-06 07:30 | 60.0 |
| 26509 | 2026-01-26 16:45 | 60.0 |

**Smallest positive rain values removed**: 32.5 mm (removed by `rain_counter_rebound`; `rain_after_gap` removed 3 readings, `rain_counter_rebound` 1; all listed in section 2).

**`rain_after_gap` candidates spared because the storm continued** (1): a catch-up is a single lump followed by silence; these are followed by a different reading of >= 10 mm (or are a gauge's latest reading), so they look like a storm that began during the gap.

| graph_id | time_local | rain_15min_mm | next_reading_mm |
| --- | --- | --- | --- |
| 27233 | 2025-03-06 00:00 | 30.5 | 24.0 |

**`rain_stuck`** removed 0 readings that no earlier rule had caught. Repeated implausible values (already removed by `rain_implausible`): 26512 repeats 1534.5 mm 3 times; 26513 repeats 965.5 mm 6 times. The stuck rule is a guard for a gauge that sticks below the implausible limit.

**12 Nov 2024, 06:00-12:00:** 24 readings flagged at any station (26509, 26558, rule rain_implausible, wl_unresponsive). PEKANMERU river level and the rain gauges within 10 km are unchanged (regression test `tests/test_qc.py::test_12_nov_2024_storm_is_untouched`, and section 3a).

**`wl_spike`**: 132 readings at 9 stations; the most are {'3115080_': 75, '3115084_': 25, '3115083_': 9}. Flagged values range from -6.58 m to 37.65 m. 7 flagged values are negative: each is a single-reading plunge below its neighbours, not a tidal swing. 13 flagged reading(s) sit directly next to another flagged reading (a burst of two or more bad readings, or a good reading between two spikes).

**`rain_counter_rebound`**: 1 readings removed after a counter dip, largest 32.5 mm.

## 3a. `wl_unresponsive`: evidence and false-positive risk

**12 Nov 2024, 06:00-12:00:** Kg. Perepat (26558) read -0.78 m throughout while Pekan Meru rose; 23 readings of 26558 are flagged (from 06:00), 0 readings of PEKANMERU are flagged (regression test `tests/test_qc_unresponsive.py::test_12_nov_2024_26558_is_flagged_and_pekan_meru_is_not`).

**Flags per station** (runs = separate flat stretches; the three stations with most flags are examined below):

| graph_id | name | readings | first | last | runs | gauges_within_radius |
| --- | --- | --- | --- | --- | --- | --- |
| 26558 | Kg. Perepat, Kapar | 9982 | 2024-08-05 | 2026-09-26 | 47 | 4 |
| PEKANMERU | Pekan Meru | 247 | 2024-05-08 | 2026-09-10 | 6 | 8 |
| 3015089_ | Tugu Keris | 52 | 2026-03-31 | 2026-04-20 | 6 | 14 |
| 3115084_ | Kg. Melayu Subang | 21 | 2025-01-04 | 2025-04-27 | 4 | 8 |

**26558 Kg. Perepat, Kapar** (level range -1.19 to 1.08 m); the 8 longest runs:

| run_start | readings | flat_level_m | rain_3h_90min_before_start_mm | max_rain_3h_90min_before_in_run_mm | first_level_after_run_m |
| --- | --- | --- | --- | --- | --- |
| 2025-12-13 19:45 | 3075 | 0.36 | 30.0 | 62.0 | 0.34 |
| 2024-10-31 03:00 | 1353 | -0.78 | 43.0 | 79.0 | -0.8 |
| 2024-08-05 18:15 | 1320 | -0.78 | 30.5 | 45.0 | -0.8 |
| 2026-06-14 18:45 | 740 | 0.36 | 55.0 | 71.5 | 0.34 |
| 2024-11-17 17:30 | 389 | -0.78 | 34.5 | 65.0 | 0.36 |
| 2024-08-20 12:45 | 364 | -0.78 | 51.5 | 96.5 | -0.81 |
| 2024-09-29 16:45 | 336 | -0.78 | 51.5 | 54.0 | -0.81 |
| 2024-09-07 23:45 | 296 | -0.78 | 31.0 | 51.0 | -0.8 |

**PEKANMERU Pekan Meru** (level range 2.69 to 4.76 m); the 6 longest runs:

| run_start | readings | flat_level_m | rain_3h_90min_before_start_mm | max_rain_3h_90min_before_in_run_mm | first_level_after_run_m |
| --- | --- | --- | --- | --- | --- |
| 2024-06-10 17:00 | 107 | 2.83 | 31.0 | 37.0 | 2.85 |
| 2026-09-09 09:00 | 70 | 2.93 | 30.5 | 30.5 | 2.91 |
| 2025-02-26 22:15 | 26 | 2.97 | 31.5 | 61.5 | 2.94 |
| 2026-01-03 20:30 | 22 | 3.07 | 44.5 | 45.0 | 3.05 |
| 2026-04-09 07:45 | 12 | 2.9 | 33.5 | 37.0 | 2.89 |
| 2024-05-08 21:00 | 10 | 2.9 | 31.0 | 39.0 | 2.92 |

**3015089_ Tugu Keris** (level range 0.83 to 4.82 m); the 6 longest runs:

| run_start | readings | flat_level_m | rain_3h_90min_before_start_mm | max_rain_3h_90min_before_in_run_mm | first_level_after_run_m |
| --- | --- | --- | --- | --- | --- |
| 2026-04-15 18:45 | 14 | 2.17 | 37.5 | 38.0 | 2.14 |
| 2026-04-18 18:30 | 13 | 2.17 | 32.5 | 36.5 | 2.16 |
| 2026-04-17 19:30 | 10 | 2.17 | 30.0 | 36.5 | 2.16 |
| 2026-03-31 18:30 | 9 | 2.17 | 32.0 | 69.0 | 2.16 |
| 2026-04-13 19:15 | 3 | 2.17 | 39.0 | 48.5 | 2.14 |
| 2026-04-20 20:15 | 3 | 2.17 | 63.0 | 63.0 | 2.13 |

**Tidal stations**: a tidal level swings with the 12.4 h tide, so its level at lag 25 (6.25 h) is anti-correlated with now. 2 of 15 river stations have lag-25 autocorrelation < -0.2 (3014080_, PANDAMARAN); 0 of their readings are flagged. No exclusion is needed.

| graph_id | name | lag25_autocorr | flagged_readings |
| --- | --- | --- | --- |
| 3014080_ | Bandar Klang | -0.74 | 0 |
| PANDAMARAN | P/A Pandamaran | -0.26 | 0 |
| DESAKEMUNING | Taman Desa Kemuning | 0.18 | 0 |
| 3015084_ | Taman Sri Muda | 0.19 | 0 |
| 3015001_ | Puchong Drop | 0.32 | 0 |

**What a flag does downstream**: the value becomes NaN. The rule engine forward-fills a level for 2 h, so a station goes stale only after that; the township's river rule then has no reading from it, and confidence is `low` only when no township station reports. The ML features have no forward-fill and lose the readings at once. A wrong flag can therefore hide a rising river. Two guards limit it: a flat level at or above the station's alert level is never flagged (a gauge stuck high or a plateau in a flood keeps its value), and the rain window ends 90 min before the reading so a slow river has time to answer.

**False-positive risks** (read the run tables above):

- A river that is mostly base flow and drains a large or slow catchment can stay within 1.5 cm for 4.5 h after heavy rain over the catchment. The rule needs two gauges within the radius to each reach the threshold (the second-wettest decides), so a rain cell over one gauge no longer counts; a station with fewer than two gauges in range is never flagged. Before this change the largest gauge decided and Pekan Meru had 247 base-flow flags.
- A run lasts until the level moves, so it continues after the rain stops. A genuinely flat river is kept NaN until it moves.
- A gauge that is stuck for months (Kg. Perepat 26558: -0.78 m, then 0.36 m since 22 Nov 2024) is flagged only from the run or the dead-gauge state that proves it: the first weeks before two storms have shown no response are kept, and after every real jump the proof starts again (on the partial archive about 87 % of 26558's readings since 1 Aug 2024 are flagged, not all). A station with fewer than two rain gauges in range, or with untrusted thresholds, is not checked at all, and a gauge stuck low there reports a normal level unnoticed.
- The dead-gauge state hides readings below the alert level until the gauge shows a rise of 0.2 m; a healthy but sluggish river that missed two storms over its station would lose its first rising readings (never those at or above alert). The nearest-gauge and 48 h conditions exist to keep that from happening: without them Pekan Meru (27 Feb 2025), 3115084_ and 26039 were wrongly called dead. These guards (and the 3-reading median, without which 26558 falls from about 87 % to 70 %) were added after looking at the data, not before; the 48 h condition changes nothing on this archive. The median makes a revived gauge leave the dead state one reading late. **Live vs replay:** live flags a long-dead gauge only if the unanswered storms fall inside the history it loads (`QC_HISTORY_DAYS` = 40), so live flags less than the archive until the live loader uses that constant.
- **Live vs replay**: a run is judged on the history that is loaded. Archive cleaning (replay, training) sees the whole history; live cleaning sees the live files from `since - 1 day`, so a long stuck run whose triggering rain fell earlier is not flagged live, and live rows override archive rows in the runner. Follow-up: run QC over archive and live together.
- **Merging changes the training data** (`train_trigger.py` and the backfill load through `load_archive_readings`): the stored trigger model and its out-of-fold probabilities need retraining.

## 4. Completeness and gaps per station (after QC)

`valid_%` = non-missing readings between the station's first and last valid reading, out of the 15-min slots in that span. `longest_gap_h` = longest stretch between two valid readings.

### River level (WL)

| graph_id | name | first | last | valid_% | longest_gap_h | gap_start |
| --- | --- | --- | --- | --- | --- | --- |
| 26039 | Kg. Budiman | 2024-04-01 | 2026-10-15 | 58.6 | 7924.0 | 2024-11-26 10:45 |
| 26558 | Kg. Perepat, Kapar | 2024-04-01 | 2026-10-16 | 81.9 | 773.8 | 2025-12-13 19:30 |
| 3014080_ | Bandar Klang | 2024-04-01 | 2026-10-14 | 87.4 | 1097.2 | 2026-04-02 20:30 |
| 3015001_ | Puchong Drop | 2024-04-01 | 2026-10-15 | 86.7 | 1726.0 | 2026-08-03 14:30 |
| 3015083_ | TTDI Jaya | 2024-04-01 | 2026-10-15 | 94.0 | 452.5 | 2025-03-29 15:15 |
| 3015084_ | Taman Sri Muda | 2024-04-01 | 2026-10-14 | 84.3 | 1273.5 | 2024-07-02 14:45 |
| 3015089_ | Tugu Keris | 2024-04-01 | 2026-10-14 | 94.3 | 452.5 | 2025-03-29 15:15 |
| 3016080_ | Kg. Gandhi | 2024-04-01 | 2026-10-15 | 62.5 | 7762.2 | 2024-10-06 01:30 |
| 3017107_ | Seri Kembangan | 2024-04-01 | 2026-10-15 | 87.7 | 452.8 | 2025-03-29 15:15 |
| 3115080_ | Paya Jaras | 2024-04-01 | 2026-10-15 | 42.3 | 11404.2 | 2024-07-09 11:30 |
| 3115083_ | Taman Mayang | 2024-04-01 | 2026-10-15 | 45.2 | 10560.5 | 2024-08-13 15:15 |
| 3115084_ | Kg. Melayu Subang | 2024-04-01 | 2026-10-15 | 78.6 | 815.2 | 2025-02-08 15:45 |
| DESAKEMUNING | Taman Desa Kemuning | 2024-04-01 | 2026-10-15 | 91.3 | 939.8 | 2025-03-29 15:15 |
| PANDAMARAN | P/A Pandamaran | 2024-04-01 | 2026-10-16 | 93.4 | 452.8 | 2025-03-29 15:15 |
| PEKANMERU | Pekan Meru | 2024-04-01 | 2026-10-16 | 93.7 | 402.2 | 2025-03-29 15:15 |

### Rain (RF)

| graph_id | name | first | last | valid_% | longest_gap_h | gap_start |
| --- | --- | --- | --- | --- | --- | --- |
| 2414401_ | SMK Jalan Kebun | 2024-01-01 | 2026-10-15 | 96.8 | 448.0 | 2025-03-29 15:00 |
| 26038 | Taman Sentosa | 2024-01-01 | 2026-10-14 | 83.1 | 3292.8 | 2026-04-23 10:30 |
| 26039 | Kg. Budiman | 2024-01-01 | 2026-10-15 | 92.1 | 448.0 | 2025-03-29 15:00 |
| 26497 | Kg. Berembang (SMART) | 2024-01-05 | 2026-10-15 | 85.4 | 2923.5 | 2024-08-08 17:00 |
| 26507 | Empangan Batu (F2) | 2026-08-01 | 2026-10-16 | 99.9 | 1.0 | 2026-09-19 07:00 |
| 26509 | Kg. Sg. Tua Empangan Batu (F2) | 2024-01-01 | 2026-10-16 | 77.5 | 2676.0 | 2025-09-10 01:00 |
| 26511 | Empangan Klang (F2) | 2024-01-23 | 2026-10-16 | 91.5 | 488.8 | 2024-04-12 03:30 |
| 26512 | Ladang Edinburgh (F2) | 2024-01-01 | 2026-10-16 | 83.5 | 1212.2 | 2024-01-01 05:15 |
| 26513 | Sentul (F2) | 2024-01-01 | 2026-10-16 | 75.5 | 1912.8 | 2024-02-21 17:15 |
| 26514 | Lembah Jaya (F2) | 2024-01-01 | 2026-10-16 | 96.3 | 446.2 | 2025-03-29 15:00 |
| 26516 | Taman Cuepacs (F2) | 2024-05-16 | 2026-10-16 | 66.9 | 2779.2 | 2025-08-14 14:45 |
| 26517 | Lembah Keramat (F2) | 2024-01-01 | 2024-03-31 | 52.3 | 744.5 | 2024-02-09 16:30 |
| 26558 | Kg. Perepat, Kapar | 2024-01-01 | 2026-10-16 | 96.1 | 448.0 | 2025-03-29 15:00 |
| 27232 | Sri Manja | 2024-01-05 | 2026-10-15 | 90.0 | 448.0 | 2025-03-29 15:00 |
| 27233 | Kg. Lombong | 2024-01-05 | 2026-10-15 | 89.1 | 448.0 | 2025-03-29 15:00 |
| 27234 | P/A Kg. Sg. Kandis | 2024-01-05 | 2026-10-15 | 87.4 | 2192.5 | 2025-08-08 10:30 |
| 27928 | Bandar Klang (F2) | 2025-02-03 | 2026-10-16 | 93.4 | 447.8 | 2025-03-29 15:00 |
| 27946 | Kg. Delek (F2) | 2025-11-05 | 2026-10-16 | 99.3 | 53.2 | 2026-08-18 10:30 |
| 27948 | SK Bukit Kemuning (F2) | 2025-11-06 | 2026-10-16 | 96.7 | 168.5 | 2026-03-05 15:15 |
| 28043 | Sg. Rasau AJ (F2) | 2025-01-22 | 2026-10-16 | 89.4 | 509.2 | 2026-03-23 07:45 |
| 2915118_ | Ayer Hitam Puchong | 2024-01-01 | 2026-10-15 | 89.9 | 448.0 | 2025-03-29 15:00 |
| 3014080_ | Bandar Klang | 2024-01-01 | 2026-10-14 | 91.5 | 1097.5 | 2026-04-02 20:30 |
| 3015001_ | Puchong Drop | 2024-01-01 | 2026-10-15 | 96.2 | 448.2 | 2025-03-29 14:45 |
| 3015083_ | TTDI Jaya | 2024-01-01 | 2026-10-15 | 97.0 | 448.2 | 2025-03-29 14:45 |
| 3015084_ | Taman Sri Muda | 2024-01-01 | 2026-10-14 | 96.3 | 448.2 | 2025-03-29 14:45 |
| 3015089_ | Tugu Keris | 2024-01-01 | 2026-10-14 | 96.3 | 448.2 | 2025-03-29 14:45 |
| 3015440_ | IOI Puchong Jaya | 2024-01-01 | 2026-10-15 | 92.8 | 448.0 | 2025-03-29 15:00 |
| 3016077_ | Jalan 222 | 2024-01-01 | 2026-10-15 | 89.9 | 1664.8 | 2025-08-30 04:30 |
| 3016080_ | Kg. Gandhi | 2024-01-01 | 2026-10-15 | 96.7 | 448.0 | 2025-03-29 15:00 |
| 3017107_ | Seri Kembangan | 2024-01-01 | 2026-10-15 | 91.0 | 448.0 | 2025-03-29 15:00 |
| 3114087_ | Empangan Tasik Subang Meru | 2024-01-01 | 2026-10-14 | 95.2 | 448.2 | 2025-03-29 14:45 |
| 3115080_ | Paya Jaras | 2024-01-01 | 2026-10-14 | 93.4 | 448.0 | 2025-03-29 15:00 |
| 3115083_ | Taman Mayang | 2024-01-01 | 2026-10-15 | 96.0 | 448.0 | 2025-03-29 15:00 |
| 3115084_ | Kg. Melayu Subang | 2024-01-01 | 2026-10-15 | 88.7 | 448.5 | 2025-03-29 15:00 |
| 3116074_ | Leboh Pasar | 2024-01-01 | 2026-06-30 | 93.7 | 446.2 | 2025-03-29 15:00 |
| 3117005_ | Kg. Air Panas | 2024-01-01 | 2026-10-15 | 7.6 | 10844.5 | 2025-05-23 11:30 |
| 3117403_ | Jln. Tun Razak (Sg. Bunus) | 2024-01-01 | 2026-10-15 | 97.3 | 446.2 | 2025-03-29 15:00 |
| DESAKEMUNING | Taman Desa Kemuning | 2024-01-01 | 2026-10-15 | 96.4 | 448.0 | 2025-03-29 15:00 |
| JLNBENTENGKAPAR | Jln. Benteng Kapar | 2024-01-01 | 2026-10-16 | 93.3 | 448.0 | 2025-03-29 15:00 |
| KGDELEK | Kg. Delek | 2024-01-01 | 2026-10-15 | 66.6 | 4318.2 | 2024-11-23 07:00 |
| KGRANTAUPANJANG | Kg. Rantau Panjang | 2024-01-01 | 2026-10-16 | 95.8 | 448.0 | 2025-03-29 15:00 |
| KOTADAMANSARA | Kota Damansara | 2024-01-01 | 2026-10-15 | 94.1 | 448.2 | 2025-03-29 14:45 |
| LDGELMINA | Ladang Elmina | 2024-01-01 | 2026-10-16 | 93.8 | 479.2 | 2024-02-08 12:45 |
| PANDAMARAN | P/A Pandamaran | 2024-01-01 | 2026-10-16 | 96.6 | 448.0 | 2025-03-29 15:00 |
| PEKANMERU | Pekan Meru | 2024-01-01 | 2026-10-16 | 96.6 | 402.5 | 2025-03-29 15:00 |
| SELATMUARA | Selat Muara | 2024-01-01 | 2026-10-16 | 96.1 | 448.2 | 2025-03-29 14:45 |
| SMKRAJALUMU | SMK Raja Lumu | 2024-01-01 | 2026-10-14 | 89.7 | 588.2 | 2024-08-24 02:45 |
| TAMANBOTANI | Taman Botani | 2024-01-01 | 2026-10-15 | 96.5 | 448.2 | 2025-03-29 14:45 |
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
