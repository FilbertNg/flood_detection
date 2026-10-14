# Flood-Ready Township — Training Data Specification

v2.3 · 14 Oct 2026 · @Filbert

> **v2.3 changes:** new **Table D `ml_trigger_train.parquet`** for the ML-first trigger: one row per river station per 15 min, labelled by whether the river crosses its own warning level within 1 / 2 h (labels come from the data, no news needed). Table B (news-labelled) becomes the optional street flash-flood classifier.
>
> **v2.2 changes:** gridded model rain missed the 12 Nov 2024 storm (≤ 6.8 mm anywhere in a 30 km box around Klang, across 8 Open-Meteo sources, vs 79 mm at the Kg Perepat gauge), so **Table B is now built from JPS station rain** (Jan 2024 onward) and Dataset 2 is reduced to forecasts, warnings and a bias study. The history archive uses monthly chunks and selects stations by district. T2–T4 are implemented and running (`scripts/run_loggers.py`, `scripts/archive_jps_history.py`). Sg Binjai read 2.94 m at 08:00 on 12 Nov 2024 (not 2.93).
>
> **v2.1 changes:** the Telegram bot report is replaced by **Resident app answers and flood reports** (Dataset 7), which feed the live benchmark and, after review, the labels (`source_type = app_report`). Rain-at-onset per street is added for the Admin app's improvement suggestions.
>
> **v2 changes:** JPS Public Infobanjir replaces the data.gov.my flood API, which has been frozen since Feb 2024. This adds a 15-minute station history archive (Jan 2024 onward). The trigger table is now district-level with day-level labels, built on the same Open-Meteo source as the live system. Leaking features are removed. Tide is computed for every hour. Map dry samples follow the road network, and BBR is held out for validation. Outlook evaluation uses real day-ahead forecasts. Every label needs an evidence quote. The reasons are in *Flood-Ready Township — Plan Review*.

## Purpose and how to use this doc

This spec tells Claude Code exactly which files to build, from which open sources, so the team ends up with model-ready tables for *where* floods happen, *when* they happen, and the station data that the rules and the demo replay run on.

**Output of the whole pipeline**

| File | Grain | Used for |
| --- | --- | --- |
| `data/final/events.csv` | One row per flood observation (human-checked) | Labels for everything |
| `data/final/susceptibility_train.parquet` | One row per point (flood or dry sample) | Susceptibility map (where) |
| `data/final/trigger_train.parquet` | One row per district per hour | District model (when) |
| `data/final/station_15min.parquet` | One row per JPS station per 15 min | Station rules, replay, evaluation |
| `data/final/ml_trigger_train.parquet` | One row per river station per 15 min (below warning) | **ML trigger** (main model) |
| `data/final/alert_outcomes.parquet` | One row per alert, with resident and sensor outcome | Live benchmark, Admin statistics, suggestions, new labels |

**How to use it with Claude Code**

1. Create an empty repo and paste this doc into it as `DATA_SPEC.md`.
2. Give Claude Code one task from the *Claude Code task list* at a time; ask it to write a script under `scripts/` and a short test.
3. After each scraping task, a human reviews the output before the next step, especially flood labels.
4. Keep raw downloads under `data/raw/` with the download date in the filename; never edit raw files by hand.
5. **Start T2–T4 today.** Live logs can't be recreated later, and the Infobanjir history endpoints are undocumented, so they could change without notice.

**Pilot focus:** Bandar Bukit Raja (Klang) first, because it has the best-documented SDP flood history. The map covers BBR plus at most two other SDP townships for the MVP. The district model uses flash floods from all of Klang, Petaling and Kuala Lumpur.

## Study area and known SDP flood incidents

Bandar Bukit Raja has at least four documented flash floods since 2017, plus a residents' memorandum naming specific streets, which makes it the pilot township.

**SDP townships to cover** (verify the list on [simedarbyproperty.com](https://www.simedarbyproperty.com) before use; Claude Code should geocode each with OSM/Nominatim and save a polygon, or a 3 km buffer around the centre)

| Township | District / state | Priority |
| --- | --- | --- |
| Bandar Bukit Raja | Klang, Selangor | Pilot (map + model) |
| Subang Jaya / USJ | Petaling, Selangor | High (map candidate) |
| City of Elmina (incl. Denai Alam, Bukit Subang) | Petaling (Shah Alam), Selangor | High (map candidate) |
| Bukit Jelutong | Petaling (Shah Alam), Selangor | High (labels) |
| Ara Damansara | Petaling, Selangor | Medium (labels) |
| Putra Heights | Petaling, Selangor | Medium (labels) |
| Saujana Impian | Hulu Langat (Kajang), Selangor | Low |
| Melawati | Gombak / Ampang Jaya, Selangor | Low |
| Serenia City | Sepang, Selangor | Low |
| Nilai Impian, Bandar Ainsdale | Seremban, Negeri Sembilan | Low |

**Named JPS stations per township.** Save these in `config/townships.yaml`; don't rely on a radius alone. Radius cut-offs are fragile: Kg. Perepat, the station quoted in both headline events, is about 9.5 km from the geocoded BBR centre, just inside a 10 km radius, and Telok Gong is about 16 km away. The old data.gov.my `station_code` usually equals the Infobanjir graph ID (e.g. `PEKANMERU`, `TELOKGONG`), so its lat/lon list can locate stations. *Graph ID* is the `stationid` used by the Infobanjir graph and history endpoints, and it is often different from the official station code.

| Township | Station | Official code | Graph ID | Type | Status |
| --- | --- | --- | --- | --- | --- |
| BBR | Sg. Kapar Kechil di Kg. Perepat, Kapar | 0220301RF / 0220301WL | `26558` | RF + WL | Verified (rain history 12 Nov 2024) |
| BBR | Sg. Binjai di Pekan Meru | 3112401 | `PEKANMERU` | WL (thresholds 2.80 / 3.80 / 4.00 / 4.20 m) | Verified (WL history 12 Nov 2024) |
| BBR | Kg. Rantau Panjang | — | `KGRANTAUPANJANG` | RF | Seen in live table; verify |
| BBR | Telok Gong | 2913001 | `TELOKGONG` | RF | Seen in live table; verify |
| BBR | P/A Pandamaran | 3014002 | `PANDAMARAN` | RF + WL | Seen in live table; verify |
| BBR | Jln. Benteng Kapar | 3013002 | `JLNBENTENGKAPAR` | RF | Seen in live table; verify |
| BBR | Sg. Klang di Bandar Klang | — | find | RF + WL | Find graph ID |
| Subang Jaya / USJ | USJ 1 | — | `USJ1` | RF | Seen in live table; verify |
| City of Elmina | Ladang Elmina | — | `LDGELMINA` | RF | Seen in live table; verify |

**Seed incidents already found (start `events.csv` with these)**

| Date | Location | SDP township | What happened | Readings | JPS 15-min data | Source |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-04-23, ~05:44 | USJ 23 Badminton Centre, Subang Jaya | Subang Jaya / USJ | Car stranded in ~0.6 m water | — | Yes (pull USJ-area stations) | [The Vibes](https://www.thevibes.com/articles/news/107340/torrential-rain-sparks-flash-floods-across-klang-valley) |
| 2024-11-12, morning | Persiaran Sungai Keramat, Persiaran Batu Belah (and 5 other Klang roads) | Bandar Bukit Raja | Roads flooded 0.1–0.4 m; >3 h rain + high tide; Setia Alam, Bukit Raja, Meru up to 2 ft | **JPS series:** Kg Perepat 45 mm by 08:45, 61.5 mm by 09:00, 79 mm by 10:15; Sg Binjai 2.94 m (08:00) → 4.21 m (10:00) → peak 4.26 m (11:45). News: Kg Perepat 45 mm, Bandar Klang 23 mm, Telok Gong 12.5 mm, Kg Rantau Panjang 11.5 mm | **Yes. Held-out test and demo event** | [RTM](https://berita.rtm.gov.my/nasional/senarai-berita-nasional/senarai-artikel/banjir-kilat-tujuh-laluan-di-klang-dinaiki-air/), [Utusan](https://www.utusan.com.my/berita/2024/11/hujan-lebat-luar-biasa-punca-banjir-kilat-di-selangor-semalam/) |
| 2024-05 (memorandum) | Jalan Makyong, Jalan Sumazau, Persiaran Sungai Keramat, Persiaran Batu Belah | Bandar Bukit Raja (Phase 1–2) | Residents: flash floods ≥ 3 times/year since Dec 2021; water inside homes | — (chronic hotspot label, not a dated event) | n/a | [Sinar Harian](https://www.sinarharian.com.my/article/666626/edisi/selangor-kl/penduduk-bandar-bukit-raja-hadap-banjir-kilat-tiga-kali-setahun) |
| 2023-06-04 (Sun) | Bandar Baru Bukit Raja, Mutiara Bukit Raja, Pekan Meru | Bandar Bukit Raja | 50–100 homes, 0.1–0.5 m; >3 h rain + high tide | Kg Perepat (Kapar) 98.5 mm; Sg Binjai at Pekan Meru 4.38 m vs danger 4.2 m at 12:00 | No (before archive) | [Sinar Harian / Bernama](https://www.sinarharian.com.my/article/262088/berita/semasa/rancangan-tebatan-banjir-di-klang-dilaksana-segera---nik-nazmi) |
| 2021-12-16 to 19 | Klang and Petaling districts (widespread) | Several | Major multi-day **river** flood; worst in Shah Alam / Klang | — | No | [Wikipedia summary](https://en.wikipedia.org/wiki/2021%E2%80%932022_Malaysian_floods) |
| 2017-11-07, ~05:00 | Bandar Bukit Raja homes, near AEON Bukit Raja, Bukit Raja toll | Bandar Bukit Raja | ~3 ft water at 05:00; two men rescued from a car | MET thunderstorm warning issued 02:00 | No | [SAYS](https://pre.says.com/my/news/flash-food-in-selangor-after-heavy-downpour) |

The news value of 45 mm at Kg Perepat on 12 Nov 2024 matches the JPS running total at 08:45. News figures are often snapshots taken early in an event, not the event totals.

**Area-level watch lists (use as hotspot labels, not dated events)**

- Bukit Jelutong and Shah Alam are on Selangor Bomba's daily flash-flood observation list ([Malaysiakini, Nov 2025](https://m.malaysiakini.com/news/761546)).
- Selangor hotspots are areas that flooded ≥ 3 times in the previous 3 years ([Kosmo](https://www.kosmo.com.my/?p=568329)).

**Caution:** confirm which developer built *Mutiara Bukit Raja* before tagging it as SDP; tag it `sdp_township = Bandar Bukit Raja (adjacent)` until checked. Ara Damansara has a reported flash flood on [paultan.org](https://paultan.org/tags/flash-floods-in-malaysia/page/1/) with no date; find the date before using it.

## Dataset 1 — Flood event labels

The label table is the most valuable and the most error-prone file. Every row needs a source URL, an evidence quote and a human check.

**File:** `data/interim/events.csv` (one row per flood observation at one place) → reviewed copy in `data/final/events.csv`

| Column | Type | Example | Notes |
| --- | --- | --- | --- |
| `event_id` | string | `BBR-2024-11-12-01` | Township or district code + date + n |
| `start_time_local` | datetime (MYT, UTC+8) | `2024-11-12 09:00` | Best estimate of first flooding; blank if unknown. **Never inferred from rain data** |
| `report_time_local` | datetime | `2024-11-12 10:30` | When first reported (news, Bomba call time) |
| `date_precision` | enum | `hour` / `day` / `month` / `season` | How precise the time is |
| `place_name` | string | `Persiaran Sungai Keramat, Klang` | As written in the source |
| `lat`, `lon` | float | from geocoder | WGS84 |
| `geo_precision` | enum | `street` / `taman` / `district` | `district` rows are used only by the district model |
| `district` | string | `Klang` | Required; the district model's unit |
| `sdp_township` | string | `Bandar Bukit Raja` | Blank if not SDP |
| `flood_type` | enum | `flash` / `river` / `mixed` | Multi-day river floods (e.g. Dec 2021) are excluded from the district model |
| `flooded` | 0/1 | `1` | Label |
| `depth_m` | float | `0.4` | Max depth if stated |
| `homes_affected` | int | `100` | If stated |
| `rain_reported_mm`, `rain_station_name` | float, string | `45`, `Kampung Perepat` | Station value quoted in the source |
| `river_level_m`, `river_danger_m`, `river_station_name` | float, float, string | `4.38`, `4.2`, `Sg Binjai, Pekan Meru` | If quoted |
| `tide_mentioned` | 0/1 | `1` | For audit only. **Never a model feature** (see Dataset 5) |
| `evidence_quote` | string | `"...air naik setinggi 0.4 meter di Persiaran Sungai Keramat..."` | Exact source text supporting time, place and numbers. Required |
| `source_url` | string | URL | Required |
| `source_type` | enum | `news` / `bomba` / `hotspot_list` / `sdp_log` / `resident_group` / `app_report` | For weighting and audit |
| `source_lang` | enum | `ms` / `en` | |
| `checked_by` | string | initials | Required before use |

**Sources (in order of value)**

1. **SDP township incident / complaint logs.** Ask the mentors in week 1. They are dated, street-level and come from the sponsor.
2. **News articles.** Use Google News RSS or GDELT queries per keyword and month for 2017–2026, plus manual searches for the pilot township. Keywords: `"banjir kilat"`, `"flash flood"`, each combined with a township, a district (`Klang`, `Shah Alam`, `Petaling Jaya`, `Subang Jaya`, `Kuala Lumpur`) or a memorandum street name. Sites: Bernama, Sinar Harian, Berita Harian, Utusan, Kosmo, Harian Metro, The Star, NST, Malay Mail, FMT, RTM, The Vibes, Selangor Journal. Keep the raw text; extract only facts.
3. **Bomba (JBPM) statements** quoted in news: their call times make good `report_time_local` values.
4. **BBR residents' Facebook groups and the residents' council:** dated photos and posts of floods (store place, time and URL only; no names or faces).
5. **JPS / Bomba hotspot lists** (published each monsoon season): digitise the Selangor rows, geocode to `taman`, store with `date_precision = season`.
6. **MBDK / MBSA / Bomba Selangor social posts:** only to confirm the time and place of events already found.
7. **Resident app answers and reports** (Dataset 7): confirmed alerts and missed-flood reports, after admin review, become rows with `source_type = app_report`. The evidence quote is the report ID plus depth, time and location.

**Negative labels (`flooded = 0`)** are not scraped. They are built from rain data; see *Data quality rules*.

## Dataset 2 — Forecasts, warnings and a gridded-rain bias study

**Gridded model rain is not a model input.** On 12 Nov 2024 the best of 8 Open-Meteo sources (Historical Forecast best_match / ECMWF / GFS / ICON / JMA; archive ERA5 / ERA5-Land / IFS) showed at most 6.8 mm in 06:00–14:00 anywhere in a 30 km box around Klang, while the Kg Perepat gauge recorded 79 mm. On 23 Apr 2025 the USJ 1 gauge recorded 49.5 mm in 45 minutes, and gridded totals ranged from 4.8 to 44 mm over 20 hours. Station rain (Dataset 3) drives the Nowcast and the district model. This dataset keeps the **forecasts** (for the Outlook and the 12 h chart), the **warnings**, and a **bias study** that documents the gap.

**File:** `data/interim/weather_hourly.parquet` (one row per district point per hour)

| Column | Type | Source | Notes |
| --- | --- | --- | --- |
| `district`, `pt_id`, `lat`, `lon` | — | config | 3–5 fixed points per district (incl. each township centre); district features take the **max** across points, so local storms aren't averaged away |
| `time_local` | datetime (MYT) | — | Hour ending |
| `precip_mm` | float | Open-Meteo **Historical Forecast API** (training) / **Forecast API** (live) | Same `models=` value in both, recorded in `source_model` |
| `precip_prob_pct` | float | Same | |
| `soil_moisture_top` | float | Same, if available (top soil layer; variable name differs by model) | Weak signal under concrete; keep, expect low importance |
| `fcst_day1_precip_mm` | float | **Previous Runs API** `precipitation_previous_day1` | Forecast made 24 h earlier; from Jan 2024. Outlook evaluation only |
| `source_model` | string | — | e.g. `ecmwf_ifs`, `best_match` |

**Bias check (evaluation only, not model input):** `data/interim/rain_bias.parquet` compares, for each station-equipped event from 2024 onward, Infobanjir station rain against Open-Meteo gridded rain, the ECMWF IFS 9 km archive and NASA GPM IMERG (0.1°, 30 min; free Earthdata login). Report how much gridded rain underestimates station peaks.

**Derived features (computed, not downloaded)**

| Feature | Definition |
| --- | --- |
| `g_rain_*` | Gridded rolling sums, **bias study only** |
| `fcst_rain_next_3h/6h/12h` | Live system only (shown on screens, used by the Outlook). **Not** a training feature for the district model |
| `hour_of_day`, `month`, `is_monsoon_ne`, `is_intermonsoon` | Calendar (NE monsoon Nov–Mar; inter-monsoon Apr–May and Oct–Nov) |

**API calls**

```text
# Training history: stitched short-range forecasts (coverage from ~2021-2022), same models as live
https://historical-forecast-api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}
  &start_date={YYYY-MM-DD}&end_date={YYYY-MM-DD}
  &hourly=precipitation,precipitation_probability,soil_moisture_0_to_1cm
  &models={model}&timezone=Asia/Kuala_Lumpur

# Outlook evaluation: what was forecast 24 h earlier (from Jan 2024)
https://previous-runs-api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}
  &start_date=...&end_date=...&hourly=precipitation,precipitation_previous_day1
  &models={model}&timezone=Asia/Kuala_Lumpur

# Live (log every hourly response with fetched_at, building our own forecast archive)
https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}
  &hourly=precipitation,precipitation_probability&past_hours=72&forecast_days=2
  &models={model}&timezone=Asia/Kuala_Lumpur

# Bias check only: ECMWF IFS 9 km archive (2017+)
https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}
  &start_date=...&end_date=...&hourly=precipitation&models=ecmwf_ifs&timezone=Asia/Kuala_Lumpur
```

Check the exact model names and soil-moisture variable names against the Open-Meteo docs in T10, then pin the chosen `models=` value in `config/sources.yaml`.

**Weather warnings (live log only):** `data/raw/met_warnings/YYYY-MM-DD.parquet`. The data.gov.my Weather Warning API returns current warnings only (no history), so log every 15 minutes from today. Parse land thunderstorm / heavy-rain warnings that name Selangor, Kuala Lumpur or our districts into `met_warning_active` per district and hour. Historical MET warnings are **not** reconstructed from news, because news mentions warnings mostly on flood days and the feature would leak the label.

## Dataset 3 — JPS station data (Public Infobanjir)

The JPS Public Infobanjir website is the live and historical source for station rain and river level. The data.gov.my Flood Warning API is frozen at 23 Feb 2024 and is kept only as a fallback behind the staleness check.

**Live tables (scrape every 15 min, Selangor and KL)**

| Data | URL (base `https://publicinfobanjir.water.gov.my`) | Format |
| --- | --- | --- |
| Water level | `/aras-air/data-paras-air/aras-air-data/?state=SEL&district=ALL&station=ALL&lang=en` | Server-rendered HTML table; cells carry `data-th` names (Station ID, Station Name, District, Main Basin, Last Updated, water level, Normal, Alert, Warning, Danger); graph IDs are in `wl-graph/?stationid=` links |
| Rainfall | `/wp-content/themes/shapely/agency/searchresultrainfall.php?state=SEL&district=ALL&station=ALL&language=1&loginStatus=0` | HTML table: Station ID, Station, District, Last Updated, daily totals for the previous 6 days, rainfall from midnight, total 1 hour (now); graph IDs in `rf-graph/?stationid=` links |

For Kuala Lumpur, find the state code in the page's state dropdown. Parse columns **by header name**, not by position, and check the parse against the page on day one.

**History endpoints (archive once; undocumented)**

| Data | URL (under `/wp-content/themes/enlighten/query/`) | Response | Depth |
| --- | --- | --- | --- |
| Water level | `searchresultwaterleveldtlead.php?station={graph_id}&from=DD/MM/YYYY HH:mm&to=DD/MM/YYYY HH:mm&datafreq=15` | JSON: `info{name, normal, alert, warning, danger, count}`, `values[{dt, clean, raw, ecm, final, severity}]` | From ~Apr 2024 |
| Rainfall | `searchresultrainfalldthourlylead.php?station={graph_id}&from=…&to=…&datafreq=15` | JSON: `info{name, light, moderate, …}`, `values[{dt, raw, clean, chourly, cdaily, tdaily, cyearly, c15min}]` | From ~Jan 2024 |

**Parsing rules (confirmed on 12 Nov 2024 data):**

- The response may start with whitespace; parse from the first `{`. An empty result looks like `{"count":},]}No result`; treat it as empty, not as an error.
- Rows come every **5 minutes**. Only quarter-hour rows carry real readings. In between, `raw = -9999`, and for rainfall the `clean` / `c15min` values are **repeated** from the last quarter-hour.
- **Keep only rows where `raw != -9999`**, otherwise rain is counted three times. For rain, use `c15min` and cross-check that it equals the change in `cdaily`.
- For water level, use `final`, with `-9999` → null.
- Timestamps are local time (MYT), format `DD/MM/YYYY HH:mm`.
- Request in **calendar-month** chunks (about 1 MB, 3–5 s each; a 6-month window failed), wait at least 3 s between requests, cache every response under `data/raw/jps_hist/raw/{kind}/{graph_id}/{YYYYMMDD}_{YYYYMMDD}.json.gz` only after it parses, and never re-download a cached chunk. Parsed rows go to `data/raw/jps_hist/{kind}/{graph_id}.parquet`.

**File:** `data/final/station_15min.parquet` (one row per station per 15 min; live log + history merged)

| Column | Notes |
| --- | --- |
| `graph_id`, `station_code`, `station_name`, `district`, `lat`, `lon` | Station lookup built from the live tables (lat/lon from the old data.gov.my list or geocoding) |
| `station_type` | `RF`, `WL` or both |
| `time_local` | Quarter-hour, MYT |
| `rain_15min_mm` | From `c15min` (history) or the difference in rainfall-from-midnight (live) |
| `wl_m` | Water level; null if `-9999` |
| `wl_normal_m`, `wl_alert_m`, `wl_warning_m`, `wl_danger_m` | Station thresholds |
| `source` | `hist` / `live` / `datagovmy_fallback` |
| `source_time`, `fetched_at` | Source timestamp (MYT) and our clock (UTC) |
| `is_stale` | 1 if `fetched_at − source_time` > 2 h |

**Derived features per station and township**

- `st_rain_1h`, `st_rain_2h`, `st_rain_3h`, `st_rain_4h`: rolling sums of `rain_15min_mm`.
- `st_rain_2to4h_max`: max of the 2 h, 3 h and 4 h sums. JPS flash-flood guide input (≥ 60 mm = Warning).
- `st_rain_1h`: JPS one-hour intensity categories: light 1–10, moderate 11–30, **heavy 31–60 (Watch)**, **very heavy > 60 mm (Warning)**.
- `st_rain_24h`, `st_rain_72h_antecedent` (72 h before the current 24 h), `st_max_15min_in_1h`.
- `river_margin_m` = `wl_danger_m − wl_m` (negative = above danger); `river_level_band` = highest threshold passed; `river_rising` = 1 if `wl_m` has risen over the last 30 min.
- Per township: max across its named stations. Per district (Table B): max across all non-stale district stations, plus `n_stations_reporting`.

**Threshold check:** for every station, confirm normal < alert < warning < danger. Some stations in the old feed broke this (e.g. warning 133.33 < alert 133.93). Flag those rows and don't use them for rules.

## Dataset 4 — Terrain and land features per grid cell

Every 30 m cell in each mapped township (plus a 3 km buffer) gets fixed features that describe how easily water collects there.

**File:** `data/interim/grid_features.parquet` (one row per cell) + `data/interim/streets.gpkg`

| Column | Type | How to compute | Tool |
| --- | --- | --- | --- |
| `cell_id` | string | Row/col index on a 30 m grid, EPSG:3375 (GDM2000 Peninsular RSO) or 32647 | rasterio |
| `lat`, `lon` | float | Cell centre, WGS84 | |
| `elev_m` | float | **FABDEM** (buildings and trees removed). GLO-30 for production | rasterio |
| `slope_deg` | float | From DEM | WhiteboxTools / richdem |
| `flow_acc` | float | Flow accumulation (log-scaled), after filling depressions | WhiteboxTools / pysheds |
| `twi` | float | ln(flow_acc / tan(slope)), with a minimum slope to avoid division by zero on flat ground | WhiteboxTools |
| `hand_m` | float | Height above nearest drainage (stream network from a flow_acc threshold **plus** OSM waterways and drains burned in) | WhiteboxTools / pysheds |
| `tpi` | float | Topographic position index | WhiteboxTools |
| `dist_river_m` | float | Distance to nearest OSM waterway (river, stream, canal, drain) | GeoPandas |
| `dist_coast_m` | float | Distance to coastline | GeoPandas |
| `impervious_pct` | float | Share of ESA WorldCover "built-up" in a 90 m window | rasterio |
| `building_density` | float | OSM building footprint area / cell area | GeoPandas |
| `on_road` | 0/1 | Cell intersects an OSM road | GeoPandas |
| `baseline_index` | 1–5 | Quintiles of a HAND + TWI score (low HAND, high TWI = 5) | numpy |
| `sdp_township` | string | Spatial join with township polygons | GeoPandas |

**Visual check before any model:** plot `hand_m` and `baseline_index` for BBR with the memorandum streets overlaid. Klang is very flat, and DEM noise is similar in size to the real relief; if HAND is visibly noise, say so and lean on `dist_river_m`, `tpi` and `impervious_pct`.

**Street roll-up:** for each OSM street segment, store `street_id`, `name`, `geometry`, `baseline_max`, `baseline_mean`, and `score_max`, `score_mean` from the model (filled after the model runs).

**Downloads**

- FABDEM: University of Bristol data repository (free, CC BY-NC-SA). Copernicus GLO-30: AWS open data bucket `copernicus-dem-30m`.
- OSM: Geofabrik Malaysia extract, or Overpass API for each township bounding box.
- ESA WorldCover 2021: AWS open data bucket `esa-worldcover`.

## Dataset 5 — Tide

Both headline BBR events coincided with high tide, and BBR drains toward the tidal Sg. Klang / Kapar estuary. Tide is deterministic, so it can be computed for every past and future hour without labels and without leakage.

**File:** `data/interim/tide_hourly.parquet` (one row per hour, Port Klang)

| Column | Notes |
| --- | --- |
| `time_local` | Hour, MYT |
| `tide_height_m` | Predicted astronomical tide at Port Klang |
| `hours_to_high_tide` | Signed hours to the nearest high water |
| `is_spring_tide` | 1 within ±2 days of new or full moon |
| `source` | `pytmd` / `utide` / `jupem_table` / `openmeteo_marine` |

**Method (pick the first that works in half a day):** (1) pyTMD with a global tide model at an offshore point near Port Klang; (2) utide fitted on JUPEM's published Pelabuhan Klang tide-table values; (3) the Open-Meteo Marine API `sea_level_height_msl` at an offshore point. Its docs warn that coastal accuracy is limited, and its archive depth needs checking. Cross-check the high-water times against JUPEM tables for 12 Nov 2024 and 4 Jun 2023.

## Dataset 6 — Satellite flood extent (optional, context only)

Sentinel-1 radar sees through cloud, but change detection misses flooded built-up areas, because walls often *raise* the backscatter. The best available event (Dec 2021) was also a multi-day river flood, not a flash flood. So S1 is used **only as river-flood context on the map**, not to train or validate the flash-flood map.

**File:** `data/interim/s1_flood_20211218.tif` + `data/interim/s1_flood_points.csv`

| Step | Detail |
| --- | --- |
| Platform | Google Earth Engine (free for research/education) |
| Collection | `COPERNICUS/S1_GRD`, VV polarisation, IW mode |
| Before image | Median of 2–4 weeks before the event, same orbit direction |
| After image | First pass after the event |
| Method | Change detection: after/before ratio below a threshold (start at −3 dB), then remove permanent water (JRC Global Surface Water) and slopes > 5° |
| Output | Flood mask clipped to township buffers |

Reference: a published study mapped Shah Alam this way ([Geomatics, Natural Hazards & Risk](https://doaj.org/article/16b1580f7b6d4edcafed345237374773)).

## Dataset 7 — Alerts and resident verification (live, from the apps)

Every alert the system sends becomes a scored prediction once residents answer. This dataset is created by the backend, not scraped. It drives the Admin statistics, the improvement suggestions, and new labels.

**Tables (in the app database; exported nightly to `data/raw/app/YYYY-MM-DD/`)**

`alerts`, one row per alert sent:

| Column | Notes |
| --- | --- |
| `alert_id`, `street_id`, `township`, `horizon` (`outlook` / `nowcast`), `level` | |
| `issued_at` | MYT |
| `window_start`, `window_end` | Expected time window shown to residents |
| `fired_by` | `rule_rain` / `rule_river` / `model` / combination |
| `reasons` | Ranked list as shown (e.g. `["rain_2h=62mm@Kg Perepat", "tide_high=11:40"]`) |
| `inputs_snapshot` | JSON of station, gridded, tide and susceptibility values at issue time, for audit and replay |
| `recipients` | Number of devices pushed |
| `is_replay` | 1 for demo or replay alerts; **excluded from all statistics** |

`answers`, one row per resident answer or report:

| Column | Notes |
| --- | --- |
| `answer_id`, `device_id` (random), `street_id` | |
| `alert_id` | Null for a "Report a flood" with no active alert |
| `answer` | `yes` / `no` / `not_sure` / `report` |
| `depth` | `ankle` / `knee` / `above_knee` / null |
| `photo_path` | EXIF removed; null if none |
| `lat_100m`, `lon_100m`, `distance_to_street_m` | Optional, rounded; answers more than 1 km away are weighted down |
| `answered_at` | MYT |
| `review_status` | `pending` / `valid` / `spam` (Admin review queue) |

`sensor_events`: `device_id`, `time_local`, `level_cm`, `above_threshold`, `simulated` (1 for the MVP simulator; excluded from statistics).

**Derived: `data/final/alert_outcomes.parquet`** (one row per non-replay alert)

| Column | Definition |
| --- | --- |
| `alert_id`, `street_id`, `issued_at`, `level`, `fired_by` | From `alerts` |
| `n_yes`, `n_no`, `n_photo_yes` | Distinct devices within 3 h of `issued_at` |
| `sensor_confirmed` | Sensor above threshold within 3 h |
| `outcome` | `confirmed` (sensor, or ≥ 2 yes, or ≥ 1 yes with photo) / `not_confirmed` (≥ 3 no and 0 yes) / `unverified` |
| `first_yes_at`, `live_lead_min` | First confirmation time; `first_yes_at − issued_at` |
| `st_rain_2to4h_at_onset` | Station rain (Table C) at `first_yes_at`, used for the rain-at-onset statistics and SUG-1 |
| `hours_from_high_tide_at_onset` | From Dataset 5, used for SUG-2 |

**Missed floods:** `answers` with `answer = report`, backed by ≥ 2 devices or 1 with a photo, on a street with no Warning or Danger in the previous 3 h → `data/final/missed_floods.parquet`.

**Into the labels:** reviewed (`review_status = valid`) confirmations and missed floods are appended to `events.csv` with `source_type = app_report`, `date_precision = hour`, `geo_precision = street`, and `checked_by` set to the reviewing admin.

## Final model tables

Three tables come out of the pipeline: one row per place for the map, one row per district-hour for the district model, and one row per station per 15 minutes for the rules and the replay.

**Table A — `susceptibility_train.parquet` (where)**

| Column | From | Notes |
| --- | --- | --- |
| `point_id`, `lat`, `lon`, `sdp_township` | events / dry samples | Location |
| `elev_m`, `slope_deg`, `flow_acc`, `twi`, `hand_m`, `tpi`, `dist_river_m`, `dist_coast_m`, `impervious_pct`, `building_density`, `baseline_index` | Dataset 4 (cell containing the point) | Ground features |
| `label` | 1 = flooded (street/taman precision), 0 = dry sample | Target |
| `label_source` | `news` / `bomba` / `hotspot` / `sdp_log` / `resident` / `dry_sample` | For weighting and audit |
| `cv_block` | 1 km spatial block ID | For spatial cross-validation |
| `holdout_bbr` | 1 if inside the BBR buffer | Excluded from the **validation run**; included in the final production map |
| `event_ids` | list | Links back to `events.csv` |

**Table B — `trigger_train.parquet` (when; optional street flash-flood classifier, Should)**

| Column | From | Notes |
| --- | --- | --- |
| `district`, `time_local` | Dataset 2 | One row per district per hour |
| `d_rain_1h`, `d_rain_2to4h_max`, `d_rain_24h`, `d_rain_72h_antecedent`, `d_max_15min_in_1h` | Table C | District max over non-stale stations; the same source as live |
| `d_river_band_max`, `d_river_rising_any` | Table C | Highest river threshold passed in the district; any WL station rising |
| `n_stations_reporting` | Table C | Data coverage for that hour |
| `tide_height_m`, `hours_to_high_tide`, `is_spring_tide` | Dataset 5 | Computed for every hour |
| `hour_of_day`, `month`, `is_monsoon_ne`, `is_intermonsoon` | derived | Calendar |
| `label_flood_today` | events.csv | **Primary target:** 1 if a flash flood (`flood_type = flash`) is reported in the district on that calendar date |
| `label_flood_next_3h` | events.csv | Only for hour-precision events; null otherwise. Used for lead-time evaluation, not training |
| `event_id` | events.csv | Groups rows for leave-one-event-out |
| `negative_type` | — | `probable_negative` for non-event days (see rules) |

**Deliberately excluded from Table B** (they leak the label or don't match live data): historical `met_warning_active`, `tide_mentioned`, `susceptibility_score`, and gridded model rain. The training period starts in Jan 2024, where station history begins.

**Table D — `ml_trigger_train.parquet` (ML trigger, Must)**

| Column | From | Notes |
| --- | --- | --- |
| `graph_id`, `time_local` | Table C | One row per river station per quarter hour while the level is below its warning level |
| `d_alert_m`, `d_warning_m`, `d_danger_m` | Table C | Level minus each of the station's own thresholds (station-relative, so one model fits all stations) |
| `rise_15m`, `rise_60m`, `rise_120m` | Table C | Level change over the window |
| `rain_{1h,2h,3h,6h,24h}_{max,mean}_{10km,25km}`, `rain_72h_antecedent_max_25km` | Table C | Over rain stations within 10 / 25 km of the river station |
| `tide_height_m`, `hours_to_high_tide` | Dataset 5 | |
| `hour`, `month` | derived | |
| `cross_1h`, `cross_2h` | Table C | **Labels:** 1 if the level reaches the station's warning level within the next 1 / 2 h |
| `fold` | derived | Time-blocked fold by season; 12 Nov 2024 always in a test fold |

Rules: stations whose thresholds are out of order are excluded; features use only data at or before `time_local` (a leakage test enforces this); no station ID feature. Evidence that this works: `docs/ml-feasibility.md`.

**Table C — `station_15min.parquet`** is defined in Dataset 3. It feeds the station rules, the 12 Nov 2024 replay, and the rule-layer evaluation on 2024+ events.

**Example rows for Table B (illustrative values, not real data)**

```csv
district,time_local,d_rain_1h,d_rain_2to4h_max,d_rain_24h,d_rain_72h_antecedent,d_river_band_max,tide_height_m,hours_to_high_tide,label_flood_today,label_flood_next_3h,event_id,negative_type
Klang,2024-11-12 09:00,61.5,61.5,62.0,22.0,alert,<m>,<h>,1,1,KLG-2024-11-12-01,
Klang,2024-10-21 15:00,12.0,18.0,20.0,3.0,normal,<m>,<h>,0,,,probable_negative
```

The first row comes from a flood day; the second is a rainy hour in the same district with no flood reported, which is exactly the contrast the model must learn.

## Data quality rules, negatives and splits

Bad negatives, leaky features and leaky splits are the three ways this dataset can fool the team; each has a fixed rule.

**Label rules**

- A positive needs a source URL, an **evidence quote**, a date and a place. Street or taman precision is required for Table A; district precision is enough for Table B.
- Two reports of the same place within 6 h and 500 m are one event (deduplicate).
- Every positive is checked by a human (`checked_by` filled) before training.
- Times: convert everything to MYT (UTC+8). "Pagi tadi" / "early morning" → `date_precision = day` unless an hour is stated.
- **Never infer a start hour from rain data.** That makes the label a function of the input.
- Multi-day river floods (`flood_type = river`, e.g. Dec 2021) are excluded from Table B.

**Negative examples**

- **District model:** every district-day where some station recorded ≥ 10 mm and no flood report for that district gets `label_flood_today = 0` and `negative_type = probable_negative`. Use all of them rather than a fixed 5:1 sample, and handle imbalance with class weights. Unreported small floods exist, so these are "probably dry", not certain. Exclude 14–25 Dec 2021 and other major regional flood periods.
- **Map:** sample dry points **on roads and in built-up cells** (`on_road = 1` or `impervious_pct` > 0.5) inside township buffers, at least 200 m from any known flood point, so dry samples come from the same kind of place as the news-reported positives. Treat them as "probably dry".

**Splits and validation**

- **District model:** leave-one-event-out (all hours of an event's date in one fold). **12 Nov 2024 is always in the test set** and is the demo event.
- **Map:** spatial block cross-validation on `cv_block`. The **validation run** excludes `holdout_bbr = 1` points and is scored on BBR and the memorandum streets. The production map is then retrained on all labels.
- **False alarms:** run the full trigger (rules + model) hour by hour over a continuous period, e.g. Oct 2024 – Mar 2025, using Table C and Dataset 2, and check every Warning against news.
- **Outlook:** evaluate only with `fcst_day1_precip_mm` (2024+) or our own logged forecasts.

**Missing and stale data**

- `-9999`, `station_status = OFF` and 5-minute filler rows → null, with a `*_missing` flag column.
- A source timestamp more than 2 h old → `is_stale = 1`; the station is excluded from rules and shown greyed.
- XGBoost handles nulls; for logistic regression, impute and add the missing flag as a feature.

## Claude Code task list

Run these tasks in order; each produces one file and is small enough to review before moving on. **T2–T4 start today.**

**Repo layout**

```text
flood-ready/
  DATA_SPEC.md            # this document
  config/townships.yaml   # names, districts, bounding boxes, named stations + graph IDs
  config/sources.yaml     # pinned Open-Meteo model, endpoints, polling intervals
  scripts/                # one script per task below
  data/raw/               # untouched downloads, date-stamped
  data/interim/           # cleaned tables
  data/final/             # model-ready tables
  floodready/             # shared Python package (parsers, jobs, storage)
  tests/                  # pytest, with real-response fixtures
  notebooks/              # exploration only
```

**Tasks**

- [ ] **T1 Townships + stations.** Geocode every township with OSM Nominatim; save polygon or 3 km buffer to `config/townships.yaml` and `data/interim/townships.gpkg`. Build the station lookup from the Infobanjir live tables (code ↔ graph ID ↔ name ↔ district) and fill the named-station list per township.
- [x] **T2 Infobanjir live logger.** *Implemented: `scripts/run_loggers.py`, running since 14 Oct.* Scrapes the live water-level and rainfall tables (`SEL`, `WLH`) every 15 min → `data/raw/jps_live/{wl,rf}/YYYY-MM-DD.parquet` + raw HTML; staleness flag per station and `_status.json`. To do: MVP tick in GitHub Actions writing to Postgres (build plan B6, D2; first check that Infobanjir answers GitHub runners); after Top 10, the VPS with `deploy/systemd/` (`Restart=always`; nightly archive top-up backfills JPS gaps), watchdog alert channel, data.gov.my fallback client.
- [x] **T3 Warning + forecast loggers.** *Implemented in `scripts/run_loggers.py` (4 models × 8 points, every run kept).* data.gov.my weather warnings every 15 min → `data/raw/met_warnings/`; Open-Meteo forecast for every district point every hour → `data/raw/openmeteo_live/` (store every run).
- [ ] **T4 Infobanjir history archive.** *Implemented: `scripts/archive_jps_history.py`, first run started 14 Oct (resumable).* Named township stations first, then every station in the districts listed in `config/sources.yaml`; rain from 1 Jan 2024 and water level from 1 Apr 2024 to today, in monthly chunks, ≥ 3 s between requests, cached per chunk.
- [ ] **T5 News search.** Google News RSS / GDELT by keyword × district/township × month, 2017–2026; save raw text to `data/raw/news/`.
- [ ] **T6 Event extraction.** Use an LLM prompt to extract the `events.csv` columns from each article, **with an `evidence_quote` for every number, time and place; reject fields without one**. Write `data/interim/events_candidates.csv`, seeded with the six incidents above.
- [ ] **T7 Geocode + dedupe + review.** Geocode to street/taman, set `geo_precision` and `district`, merge reports within 6 h and 500 m. **Human review** → `data/final/events.csv`.
- [ ] **T8 DEM + OSM + land cover.** Download and clip FABDEM, OSM roads/waterways/buildings and WorldCover for each mapped township buffer.
- [ ] **T9 Terrain features + baseline.** Compute the Dataset 4 columns including `baseline_index`; write `grid_features.parquet` and `streets.gpkg`; produce the BBR HAND map with memorandum streets overlaid.
- [ ] **T10 Forecast history + bias study.** Previous Runs `previous_day1` from Jan 2024 for Outlook evaluation; Historical Forecast, IFS archive and IMERG vs station rain for every 2024+ event → `rain_bias.parquet`. Pick the forecast model to show in the apps.
- [ ] **T11 Tide.** Build `tide_hourly.parquet` (2017 → 48 h ahead); cross-check high-water times against JUPEM.
- [ ] **T12 Sentinel-1 (optional).** Earth Engine script for Dec 2021; export the flood mask as map context.
- [ ] **T13 Build Table A.** Join events + dry samples (roads/built-up) to grid features; add `cv_block` and `holdout_bbr`.
- [ ] **T14 Build Table B.** Aggregate Table C station features to district-hour, join tide, calendar and labels; mark `probable_negative` days. Run after T15.
- [ ] **T15 Build Table C.** Merge T2 live logs and T4 history into `station_15min.parquet` with derived station features and threshold checks.
- [ ] **T16 App outcomes export.** Nightly export of `alerts`, `answers` and `sensor_events`; build `alert_outcomes.parquet` and `missed_floods.parquet`; append reviewed rows to `events.csv`. Test it with synthetic answers on a replayed 12 Nov 2024 (marked `is_replay = 1`, so they never reach the statistics).
- [ ] **T17 Data report.** Notebook that prints counts per district/township/year, label balance, missing and stale rates, gridded-vs-station rain bias, a map of all events, and the 12 Nov 2024 station chart (rain, river, thresholds, tide).

**Prompt template for each task**

```text
Read DATA_SPEC.md. Do task T<n> only. Write the script in scripts/,
use the exact column names and file paths from the spec, add a short
test, run it, and show me the first 10 rows and the row count.
Do not invent data: if a value is not in the source, leave it null.
For anything extracted from text, keep the evidence quote.
```

## Licences, ethics and limits

All sources are free for a student hackathon, but some have conditions that matter if SDP later uses the system commercially.

| Source | Licence / terms | What it means for us |
| --- | --- | --- |
| JPS Public Infobanjir | Public government website; history endpoints undocumented, no published API terms | Scrape politely (≥ 3 s between history requests, live every 15 min), cache, credit JPS on every screen, don't republish bulk raw data; ask JPS before any production use |
| data.gov.my APIs | Open government data; rate limited (Weather: 4 req/min without token, 10 with) | Polling every 15 min is well within the limit. *Token request is optional* |
| Open-Meteo | Data CC BY 4.0; free API tier is non-commercial | Fine for the hackathon; production needs a paid plan or another source |
| OpenStreetMap | ODbL | Credit "© OpenStreetMap contributors" on maps |
| Copernicus DEM, Sentinel-1 | Free and open with attribution | Credit Copernicus |
| FABDEM | CC BY-NC-SA | Non-commercial; swap to GLO-30 for production |
| ESA WorldCover | CC BY 4.0 | Credit ESA |
| NASA GPM IMERG | Free with Earthdata login | Credit NASA |
| News articles | Copyrighted | Store only extracted facts, evidence quotes and URLs; do not republish article text |
| Residents' group posts | Personal data (PDPA) | Keep only place, time and URL; no names or faces |
| Resident app answers / reports | Personal data (PDPA); collected with consent in the app | Random device ID only; location rounded to ~100 m; photos with EXIF removed and never shown publicly; delete on unsubscribe |

**Ethics**

- Scrape politely: respect robots.txt, wait between requests, cache pages.
- Do not collect names or photos of flood victims; keep only place, time and measurements.
- Be careful about calling SDP townships "flood-prone" in public material. Frame findings as "where we monitor first" and share them with SDP before publishing.

**Limits to state in the pitch**

- Labels come from news, official lists and residents, so small floods that nobody reported are missing.
- Station history only starts in 2024, so the trigger is trained on 2024–2026 events; older events are map labels and news-quoted checks.
- Gridded model rain misses short tropical storms (shown on 12 Nov 2024), so forecasts give only a medium-confidence Outlook.
- The 30 m DEM cannot see drains, kerbs or walls, and Klang is very flat.

## Sources

- [JPS Public Infobanjir — live and historical station data](https://publicinfobanjir.water.gov.my/)
- [data.gov.my — Weather API](https://developer.data.gov.my/realtime-api/weather)
- [Open-Meteo — Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api) · [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api) · [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) · [Marine API](https://open-meteo.com/en/docs/marine-weather-api)
- [Sinar Harian — Bandar Bukit Raja residents' memorandum (25 May 2024)](https://www.sinarharian.com.my/article/666626/edisi/selangor-kl/penduduk-bandar-bukit-raja-hadap-banjir-kilat-tiga-kali-setahun)
- [Sinar Harian / Bernama — 4 Jun 2023 Klang flood (6 Jun 2023)](https://www.sinarharian.com.my/article/262088/berita/semasa/rancangan-tebatan-banjir-di-klang-dilaksana-segera---nik-nazmi)
- [RTM — Klang roads flooded, 12 Nov 2024](https://berita.rtm.gov.my/nasional/senarai-berita-nasional/senarai-artikel/banjir-kilat-tujuh-laluan-di-klang-dinaiki-air/)
- [Utusan — Selangor flash floods, 12 Nov 2024](https://www.utusan.com.my/berita/2024/11/hujan-lebat-luar-biasa-punca-banjir-kilat-di-selangor-semalam/)
- [The Vibes — Klang Valley flash floods, 23 Apr 2025](https://www.thevibes.com/articles/news/107340/torrential-rain-sparks-flash-floods-across-klang-valley)
- [SAYS — Bandar Bukit Raja flash flood, Nov 2017](https://pre.says.com/my/news/flash-food-in-selangor-after-heavy-downpour)
- [Malaysiakini — Selangor flash-flood watch list (Nov 2025)](https://m.malaysiakini.com/news/761546)
- [Kosmo — Selangor hotspot criteria](https://www.kosmo.com.my/?p=568329)
- [Wikipedia — 2021–22 Malaysian floods](https://en.wikipedia.org/wiki/2021%E2%80%932022_Malaysian_floods)
- [Geomatics, Natural Hazards & Risk — Shah Alam Sentinel-1 flood mapping](https://doaj.org/article/16b1580f7b6d4edcafed345237374773)
- [paultan.org — flash flood reports incl. Ara Damansara](https://paultan.org/tags/flash-floods-in-malaysia/page/1/)
