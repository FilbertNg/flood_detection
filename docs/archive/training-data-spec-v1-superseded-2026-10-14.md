# Flood-Ready Township — Training Data Specification

Oct 14, 2026 · @Filbert

## Purpose and how to use this doc

This spec tells Claude Code exactly which files to build, from which open sources, so the team ends with two model-ready tables: one for *where* floods happen and one for *when*.

**Output of the whole pipeline**

| File | Grain | Used to train |
| --- | --- | --- |
| `data/final/susceptibility_train.parquet` | One row per point (flood or non-flood location) | Susceptibility model (where) |
| `data/final/trigger_train.parquet` | One row per location per hour | Trigger model (when) |
| `data/final/events.csv` | One row per flood event (human-checked) | Labels for both |

**How to use it with Claude Code**

1. Create an empty repo and paste this doc into it as `DATA_SPEC.md`.
2. Give Claude Code one task from *Claude Code task list* at a time; ask it to write a script under `scripts/` and a short test.
3. After each scraping task, a human reviews the output CSV before the next step (especially flood labels).
4. Keep raw downloads under `data/raw/` with the download date in the filename; never edit raw files by hand.

**Pilot focus:** Bandar Bukit Raja (Klang) first, because it has the best-documented SDP flood history. Other SDP townships are added as extra labelled locations.

## Study area and known SDP flood incidents

Bandar Bukit Raja has at least four documented flash floods since 2017 plus a residents' memorandum naming specific streets, which makes it the pilot township.

**SDP townships to cover** (verify the list on [simedarbyproperty.com](https://www.simedarbyproperty.com) before use; Claude Code should geocode each with OSM/Nominatim and save a polygon or a 3 km buffer around the centre)

| Township | District / state | Priority |
| --- | --- | --- |
| Bandar Bukit Raja | Klang, Selangor | Pilot |
| Bukit Jelutong | Petaling (Shah Alam), Selangor | High |
| Subang Jaya / USJ | Petaling, Selangor | High |
| City of Elmina (incl. Denai Alam, Bukit Subang) | Petaling (Shah Alam), Selangor | High |
| Ara Damansara | Petaling, Selangor | Medium |
| Putra Heights | Petaling, Selangor | Medium |
| Saujana Impian | Hulu Langat (Kajang), Selangor | Medium |
| Melawati | Gombak / Ampang Jaya, Selangor | Low |
| Serenia City | Sepang, Selangor | Low |
| Nilai Impian, Bandar Ainsdale | Seremban, Negeri Sembilan | Low |

**Seed incidents already found (start `events.csv` with these)**

| Date | Location | SDP township | What happened | Readings reported | Source |
| --- | --- | --- | --- | --- | --- |
| 2025-04-23, \~05:44 | USJ 23 Badminton Centre, Subang Jaya | Subang Jaya / USJ | Car stranded in \~0.6 m water | — | [The Vibes](https://www.thevibes.com/articles/news/107340/torrential-rain-sparks-flash-floods-across-klang-valley) |
| 2024-11-12, morning | Persiaran Sungai Keramat, Persiaran Batu Belah (and 5 other Klang roads) | Bandar Bukit Raja | Roads flooded 0.1–0.4 m; >3 h rain + high tide; Setia Alam, Bukit Raja, Meru up to 2 ft | Kg Perepat 45 mm, Bandar Klang 23 mm, Telok Gong 12.5 mm, Kg Rantau Panjang 11.5 mm | [RTM](https://berita.rtm.gov.my/nasional/senarai-berita-nasional/senarai-artikel/banjir-kilat-tujuh-laluan-di-klang-dinaiki-air/), [Utusan](https://www.utusan.com.my/berita/2024/11/hujan-lebat-luar-biasa-punca-banjir-kilat-di-selangor-semalam/) |
| 2024-05 (memorandum) | Jalan Makyong, Jalan Sumazau, Persiaran Sungai Keramat, Persiaran Batu Belah | Bandar Bukit Raja (Phase 1–2) | Residents: flash floods ≥ 3 times/year since Dec 2021; water inside homes | — (chronic hotspot label, not a dated event) | [Sinar Harian](https://www.sinarharian.com.my/article/666626/edisi/selangor-kl/penduduk-bandar-bukit-raja-hadap-banjir-kilat-tiga-kali-setahun) |
| 2023-06-04 (Sun) | Bandar Baru Bukit Raja, Mutiara Bukit Raja, Pekan Meru | Bandar Bukit Raja | 50–100 homes, 0.1–0.5 m; >3 h rain + high tide | Kg Perepat (Kapar) 98.5 mm; Sg Binjai at Pekan Meru 4.38 m vs danger 4.2 m at 12:00 | [Sinar Harian / Bernama](https://www.sinarharian.com.my/article/262088/berita/semasa/rancangan-tebatan-banjir-di-klang-dilaksana-segera---nik-nazmi) |
| 2021-12-16 to 19 | Klang and Petaling districts (widespread) | Several | Major flood; worst in Shah Alam / Klang | — | [Wikipedia summary](https://en.wikipedia.org/wiki/2021%E2%80%932022_Malaysian_floods) |
| 2017-11-07, \~05:00 | Bandar Bukit Raja homes, near AEON Bukit Raja, Bukit Raja toll | Bandar Bukit Raja | \~3 ft water at 05:00; two men rescued from a car | MET thunderstorm warning issued 02:00 | [SAYS](https://pre.says.com/my/news/flash-food-in-selangor-after-heavy-downpour) |

**Area-level watch lists (use as hotspot labels, not dated events)**

- Bukit Jelutong and Shah Alam are on Selangor Bomba's daily flash-flood observation list ([Malaysiakini, Nov 2025](https://m.malaysiakini.com/news/761546)).
- Selangor hotspots are areas that flooded ≥ 3 times in the previous 3 years ([Kosmo](https://www.kosmo.com.my/?p=568329)).

**Caution:** confirm which developer built *Mutiara Bukit Raja* before tagging it as SDP; tag it `sdp_township = Bandar Bukit Raja (adjacent)` until checked. Ara Damansara has a reported flash flood on [paultan.org](https://paultan.org/tags/flash-floods-in-malaysia/page/1/) with no date; Claude Code should find the date before using it.

## Dataset 1 — Flood event labels

The label table is the most valuable and the most error-prone file; every row needs a source URL and a human check.

**File:** `data/interim/events.csv` (one row per flood observation at one place)

| Column | Type | Example | Notes |
| --- | --- | --- | --- |
| `event_id` | string | `BBR-2023-06-04-01` | township code + date + n |
| `start_time_local` | datetime (MYT, UTC+8) | `2023-06-04 10:00` | Best estimate of first flooding; blank if unknown |
| `report_time_local` | datetime | `2023-06-04 12:00` | When first reported (news, Bomba call time) |
| `date_precision` | enum | `hour` / `day` / `month` | How precise the time is |
| `place_name` | string | `Jalan Makyong, Bandar Bukit Raja` | As written in the source |
| `lat`, `lon` | float | `from geocoder` | Geocoded; WGS84 |
| `geo_precision` | enum | `street` / `taman` / `district` | Drop `district` rows from the susceptibility model |
| `sdp_township` | string | `Bandar Bukit Raja` | Blank if not SDP |
| `flooded` | 0/1 | `1` | Label |
| `depth_m` | float | `0.5` | Max depth if stated |
| `homes_affected` | int | `100` | If stated |
| `rain_reported_mm` | float | `98.5` | Station value quoted in the source |
| `rain_station_name` | string | `Kampung Perepat` |  |
| `river_level_m`, `river_danger_m` | float | `4.38`, `4.2` | If quoted |
| `river_station_name` | string | `Sg Binjai, Pekan Meru` |  |
| `tide_flag` | 0/1 | `1` | Source mentions high tide |
| `source_url` | string | URL | Required |
| `source_lang` | enum | `ms` / `en` |  |
| `checked_by` | string | initials | Required before use |

**Sources to scrape (in order of value)**

1. **News articles.** Search queries per township and year 2015–2026: `"banjir kilat" + "<township>"`, `"flash flood" + "<township>"`, plus street names from the memorandum. Sites: Bernama, Sinar Harian, Berita Harian, Utusan, Kosmo, Harian Metro, The Star, NST, Malay Mail, FMT, RTM, The Vibes, Selangor Journal. Extract date, time, places, depth, rain and river readings into the columns above (an LLM extraction step is fine; keep the raw text).
2. **Bomba (JBPM) statements** quoted in news: they give call times, which make good `report_time_local` values.
3. **JPS / Bomba hotspot lists** (published as images or tables each monsoon season): digitise the Selangor rows, geocode to `taman` level, store as `flooded=1` with `date_precision=season`.
4. **Social media** (X/Facebook posts from MBDK, MBSA, Bomba Selangor, JPS Selangor): only to confirm time and place of events already found in news.

**Negative labels (flooded = 0)** are made later from the rain data, not scraped: see *Data quality rules*.

## Dataset 2 — Rainfall and weather time series

Hourly rain for every labelled location, from 3 days before to 1 day after each event, plus matched non-flood rainy days.

**File:** `data/interim/weather_hourly.parquet` (one row per location per hour)

| Column | Type | Source | Notes |
| --- | --- | --- | --- |
| `loc_id` | string | events / grid | Join key |
| `time_local` | datetime (MYT) | — | Hour ending |
| `precip_mm` | float | Open-Meteo | Rain in the preceding hour |
| `precip_prob_pct` | float | Open-Meteo historical forecast | Only for 2021+ |
| `soil_moisture_0_7cm` | float | Open-Meteo archive | Wet-ground proxy |
| `source_model` | string | — | `era5`, `historical_forecast`, `imerg` |
| `met_warning_active` | 0/1 | data.gov.my weather warning (live only) | Historical: from news ("MET issued a thunderstorm warning") |
| `tide_height_m` | float | optional | Coastal Klang only; skip if no open source |

**Derived features (computed, not downloaded)**

| Feature | Definition |
| --- | --- |
| `rain_1h`, `rain_3h`, `rain_6h`, `rain_24h` | Rolling sums ending at `time_local` |
| `rain_72h_antecedent` | Sum of the 72 h before the current 24 h window |
| `max_1h_in_6h` | Peak hourly rain in the last 6 h (burst intensity) |
| `fcst_rain_next_1h/3h/6h/12h` | Forecast sums ahead (live system); historical forecast archive for training |
| `hour_of_day`, `month`, `is_monsoon_ne` | Calendar features (NE monsoon Nov–Mar) |

**API calls**

```text
# Historical (reanalysis, from 1940, ~25 km; precipitation comes from ERA5)
https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}
  &start_date={YYYY-MM-DD}&end_date={YYYY-MM-DD}
  &hourly=precipitation,soil_moisture_0_to_7cm&timezone=Asia/Kuala_Lumpur

# Archived forecasts (from 2021, finer model grid) - better for 2021+ events
https://historical-forecast-api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}
  &start_date=...&end_date=...&hourly=precipitation,precipitation_probability
  &timezone=Asia/Kuala_Lumpur

# Live forecast (next 16 days)
https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}
  &hourly=precipitation,precipitation_probability&forecast_days=2&timezone=Asia/Kuala_Lumpur
```

**Optional, better for thunderstorms:** NASA GPM IMERG (0.1°, 30-minute rain), free with an Earthdata login. Use it if ERA5 visibly misses the peak rain reported in news.

**Known limit:** reanalysis smooths short, intense storms. For events where the news quotes a station value (e.g. 98.5 mm at Kg Perepat), store that value in `events.csv` and compare it to the gridded value in the evaluation.

## Dataset 3 — JPS river level and station rain (live log)

The JPS API gives only the current reading, so a logger must start today; one month of logs is enough for live testing and the demo.

**Source:** [data.gov.my Flood Warning API](https://developer.data.gov.my/realtime-api/flood-warning), updated every 15 minutes. Values of `-9999` mean sensor fault.

**File:** `data/raw/jps_log/YYYY-MM-DD.parquet` (append every 15 min), then `data/interim/jps_stations.parquet`

| Column | API field | Notes |
| --- | --- | --- |
| `station_id`, `station_name`, `station_code` | same | Keep all three |
| `lat`, `lon`, `district`, `state`, `main_basin`, `sub_basin` | same | Filter to stations ≤ 25 km from each township |
| `station_type` | `station_type` | RF, WL or both |
| `wl_m` | `water_level_current` | Treat -9999 as missing |
| `wl_normal_m`, `wl_alert_m`, `wl_warning_m`, `wl_danger_m` | `water_level_*_level` | Thresholds per station |
| `wl_trend` | `water_level_trend` | RISING / RECEDING / NO\_CHANGE |
| `wl_indicator` | `water_level_indicator` | NORMAL / ALERT / WARNING / DANGER |
| `rain_1h_mm` | `rainfall_latest_1hr` |  |
| `rain_today_mm` | `rainfall_total_today` | Resets at midnight |
| `wl_time`, `rain_time` | `*_update_datetime` | Source timestamps |
| `fetched_at` | — | Our clock, UTC |

**Derived features per township**

- `river_margin_m` = `wl_danger_m` − `wl_m` at the nearest WL station (negative = above danger).
- `river_rising` = 1 if trend is RISING.
- `station_rain_1h_max` = max `rain_1h_mm` over RF stations ≤ 10 km.

**Stations to look for near Bandar Bukit Raja** (find the exact `station_id` in the API response): Kampung Perepat (Kapar) rainfall; Sungai Binjai at Pekan Meru water level; Bandar Klang, Telok Gong, Kampung Rantau Panjang rainfall. These names appear in past flood reports.

**Historical gap:** this API has no history. For past events, use (a) rain from Dataset 2, and (b) station values quoted in news, stored in `events.csv`.

## Dataset 4 — Terrain and land features per grid cell

Every 30 m cell in each township (plus a 3 km buffer) gets fixed features that describe how easily water collects there.

**File:** `data/interim/grid_features.parquet` (one row per cell) + `data/interim/streets.gpkg`

| Column | Type | How to compute | Tool |
| --- | --- | --- | --- |
| `cell_id` | string | Row/col index on a 30 m grid, EPSG:3375 or 32647 | rasterio |
| `lat`, `lon` | float | Cell centre, WGS84 |  |
| `elev_m` | float | Copernicus GLO-30 DEM (or FABDEM, which removes buildings and trees) | rasterio |
| `slope_deg` | float | From DEM | WhiteboxTools / richdem |
| `flow_acc` | float | Flow accumulation (log-scaled) | WhiteboxTools / pysheds |
| `twi` | float | Topographic wetness index = ln(flow\_acc / tan(slope)) | WhiteboxTools |
| `hand_m` | float | Height above nearest drainage (stream network from flow\_acc threshold) | WhiteboxTools / pysheds |
| `tpi` | float | Topographic position index (local hollow vs ridge) | WhiteboxTools |
| `dist_river_m` | float | Distance to nearest OSM waterway (river, stream, canal or drain) | GeoPandas |
| `dist_coast_m` | float | Distance to coastline (tide effect in Klang) | GeoPandas |
| `impervious_pct` | float | Share of ESA WorldCover "built-up" in a 90 m window | rasterio |
| `building_density` | float | OSM building footprint area / cell area | GeoPandas |
| `sdp_township` | string | Spatial join with township polygons | GeoPandas |

**Street roll-up:** for each OSM street segment, store `street_id`, `name`, `geometry`, and `max_score`, `mean_score` of the cells it crosses (filled after the model runs).

**Downloads**

- Copernicus GLO-30 DEM: AWS open data bucket `copernicus-dem-30m` (public, no login).
- FABDEM: University of Bristol data repository (free, CC BY-NC-SA).
- OSM: Geofabrik Malaysia extract, or Overpass API for each township bounding box.
- ESA WorldCover 2021: AWS open data bucket `esa-worldcover`.

## Dataset 5 — Satellite flood extent (validation)

Sentinel-1 radar sees through cloud, so it can map where water actually stood after big events; it is used to check the map, not to train the hourly model.

**File:** `data/interim/s1_flood_<YYYYMMDD>.tif` (1 = water that was not there before) + `data/interim/s1_flood_points.csv`

| Step | Detail |
| --- | --- |
| Platform | Google Earth Engine (free for research/education) |
| Collection | `COPERNICUS/S1_GRD`, VV polarisation, IW mode |
| Before image | Median of 2–4 weeks before the event, same orbit direction |
| After image | First pass after the event (Sentinel-1 revisits every \~6–12 days, so short flash floods may be missed) |
| Method | Change detection: after/before ratio below a threshold (start at −3 dB), then remove permanent water (JRC Global Surface Water) and slopes > 5° |
| Output | Flood mask clipped to township buffers; sample up to 200 flood and 200 dry points per event |

**Best events to try:** 2021-12-16 to 19 (long-lasting, large extent; a published study already mapped Shah Alam this way — [Geomatics, Natural Hazards & Risk](https://doaj.org/article/16b1580f7b6d4edcafed345237374773)). Short events like 2023-06-04 may have drained before the satellite passed; record "no pass in time" rather than "no flood".

Sampled points go into `susceptibility_train` with `label_source = s1` so they can be weighted separately from news labels.

## Final model tables

Two tables come out of the pipeline: one row per place for the map, and one row per place per hour for the warning model.

**Table A — `susceptibility_train.parquet` (where)**

| Column | From | Notes |
| --- | --- | --- |
| `point_id`, `lat`, `lon`, `sdp_township` | events / S1 / sampled dry points | Location |
| `elev_m`, `slope_deg`, `flow_acc`, `twi`, `hand_m`, `tpi`, `dist_river_m`, `dist_coast_m`, `impervious_pct`, `building_density` | Dataset 4 (cell containing the point) | Ground features |
| `label` | 1 = ever flooded, 0 = dry sample | Target |
| `label_source` | `news` / `hotspot` / `s1` / `dry_sample` | For weighting and audit |
| `event_ids` | list | Links back to `events.csv` |

**Table B — `trigger_train.parquet` (when)**

| Column | From | Notes |
| --- | --- | --- |
| `loc_id`, `lat`, `lon`, `sdp_township` | events | Location |
| `time_local` | Dataset 2 | Hourly timestamp (MYT) |
| `rain_1h`, `rain_3h`, `rain_6h`, `rain_24h`, `rain_72h_antecedent`, `max_1h_in_6h` | Dataset 2 | Rainfall features |
| `fcst_rain_next_3h`, `fcst_rain_next_6h`, `precip_prob_pct` | Dataset 2 (historical forecast, 2021+) | Forecast features; null before 2021 |
| `soil_moisture_0_7cm` | Dataset 2 | Wet ground |
| `met_warning_active` | news / live API | Weather warning |
| `river_margin_m`, `river_rising` | Dataset 3 (live) or `events.csv` (past) | Null where unknown |
| `tide_flag` | events / optional tide data | Coastal driver |
| `susceptibility_score` | Model A output for this location | Ground level summary |
| `elev_m`, `hand_m` | Dataset 4 | Kept raw as well |
| `hour_of_day`, `month`, `is_monsoon_ne` | derived | Calendar |
| `label_flood_next_1h`, `label_flood_next_3h`, `label_flood_next_6h` | events.csv | 1 if flooding starts within that window after `time_local` |

**Example rows (illustrative values, not real data)**

```csv
loc_id,time_local,sdp_township,lat,lon,elev_m,hand_m,rain_1h,rain_3h,rain_24h,rain_72h_antecedent,fcst_rain_next_3h,met_warning_active,river_margin_m,susceptibility_score,label_flood_next_3h
BBR-makyong,2023-06-04 08:00,Bandar Bukit Raja,<lat>,<lon>,<m>,<m>,12.0,20.5,22.0,35.0,40.0,1,0.6,5,1
BBR-makyong,2023-05-20 15:00,Bandar Bukit Raja,<lat>,<lon>,<m>,<m>,8.0,9.0,10.0,3.0,2.0,0,1.8,5,0
```

The first row is a positive (flood started within 3 h); the second is a rainy hour with no flood at the same street, which is exactly the contrast the model must learn.

## Data quality rules, negatives and splits

Bad negatives and leaky splits are the two ways this dataset can fool the team; both have fixed rules.

**Label rules**

- A positive needs a source URL, a date, and a place at `street` or `taman` precision. District-only reports are kept for the trigger model at district level but excluded from the map model.
- Two reports of the same place within 6 h are one event (deduplicate).
- Every positive is checked by a human (`checked_by` filled) before training.
- Times: convert everything to MYT (UTC+8). News "pagi tadi" / "early morning" → `date_precision = day` unless an hour is stated.

**Negative examples**

- **Trigger (when):** for each labelled location, sample rainy hours with `rain_3h` ≥ 10 mm on dates with **no** flood report anywhere in the district (search news for that date to confirm). Aim for about 5 negatives per positive.
- **Map (where):** sample dry points at random inside township buffers, at least 200 m from any known flood point; label `dry_sample`. Treat them as "probably dry", not certain.
- Never create a negative for a date in December 2021 or other major regional events.

**Splits**

- Split train / validation / test by **event date**, never randomly by row (hours from one storm must stay together).
- Hold out at least one event per year, including 2024-11-12 at Bandar Bukit Raja, for the final test.
- Keep 2023-06-04 for the demo replay; it may be in training, but say so in the pitch.

**Missing data**

- `-9999` and `station_status = OFF` → null, with a `*_missing` flag column.
- Forecast features before 2021 are null; the model must handle nulls (XGBoost does).

## Claude Code task list

Run these tasks in order; each produces one file and is small enough to review before moving on.

**Repo layout**

```text
flood-ready/
  DATA_SPEC.md            # this document
  config/townships.yaml   # names, districts, bounding boxes
  scripts/                # one script per task below
  data/raw/               # untouched downloads, date-stamped
  data/interim/           # cleaned tables
  data/final/             # model-ready tables
  notebooks/              # exploration only
```

**Tasks**

- [ ] **T1 Townships.** Geocode every township in the study-area table with OSM Nominatim; save polygon or 3 km buffer to `config/townships.yaml` and `data/interim/townships.gpkg`.
- [ ] **T2 Live JPS logger.** Script that calls the data.gov.my Flood Warning API every 15 min, keeps stations within 25 km of any township, appends to `data/raw/jps_log/`. Start it today and leave it running.
- [ ] **T3 Weather warning logger.** Same for `api.data.gov.my/weather/warning`, every 15 min.
- [ ] **T4 News scraper.** For each township × keyword (`banjir kilat`, `banjir`, `flash flood`, `air naik`) × year 2015–2026, search and fetch articles from the sites in Dataset 1; save raw HTML/text to `data/raw/news/`.
- [ ] **T5 Event extraction.** Use an LLM prompt to extract the `events.csv` columns from each article (date, time, places, depth, rain, river, tide, source); write `data/interim/events_candidates.csv`. Seed it with the six incidents in the study-area table.
- [ ] **T6 Geocode + dedupe.** Geocode place names to street/taman, set `geo_precision`, merge reports within 6 h and 500 m. **Human review** → `data/interim/events.csv`.
- [ ] **T7 DEM + OSM + land cover.** Download and clip GLO-30 (or FABDEM), OSM roads/waterways/buildings and WorldCover for each township buffer.
- [ ] **T8 Terrain features.** Compute Dataset 4 columns with WhiteboxTools/pysheds; write `grid_features.parquet` and `streets.gpkg`.
- [ ] **T9 Rain history.** For every event location: Open-Meteo archive + historical-forecast hourly data, 3 days before to 1 day after; plus matched negative dates. Write `weather_hourly.parquet`.
- [ ] **T10 Sentinel-1 (optional).** Earth Engine script for 2021-12 event; export flood mask and sampled points.
- [ ] **T11 Build Table A.** Join events + S1 + dry samples to grid features → `susceptibility_train.parquet`.
- [ ] **T12 Build Table B.** Join weather features, river margins (where known), susceptibility score and labels → `trigger_train.parquet`.
- [ ] **T13 Data report.** Notebook that prints counts per township/year, label balance, missing-value rates, and a map of all events.

**Prompt template for each task**

```text
Read DATA_SPEC.md. Do task T<n> only. Write the script in scripts/,
use the exact column names and file paths from the spec, add a short
test, run it, and show me the first 10 rows and the row count.
Do not invent data: if a value is not in the source, leave it null.
```

## Licences, ethics and limits

All sources are free for a student hackathon, but two have conditions that matter if SDP later uses the system commercially.

| Source | Licence / terms | What it means for us |
| --- | --- | --- |
| data.gov.my APIs | Open government data; rate limited (Weather: 4 req/min without token, 10 with) | Request a token from dataterbuka@jdn.gov.my; poll no faster than 15 min |
| Open-Meteo | Data CC BY 4.0; free API tier is non-commercial | Fine for hackathon; production needs a paid plan or another source |
| OpenStreetMap | ODbL | Credit "© OpenStreetMap contributors" on maps |
| Copernicus DEM, Sentinel-1 | Free and open with attribution | Credit Copernicus |
| FABDEM | CC BY-NC-SA | Non-commercial; swap to GLO-30 for production |
| ESA WorldCover | CC BY 4.0 | Credit ESA |
| News articles | Copyrighted | Store only extracted facts + URL; do not republish article text |

**Ethics**

- Scrape politely: respect robots.txt, one request every few seconds, cache pages.
- Do not collect names or photos of flood victims; keep only place, time and measurements.
- Be careful naming SDP townships as "flood-prone" in public material; frame findings as "where we would monitor first" and share with SDP before publishing.

**Limits to state in the pitch**

- Labels come from news and official lists, so small floods that nobody reported are missing.
- Reanalysis rain is coarse and smooths thunderstorms.
- The 30 m DEM cannot see drains, kerbs or walls.

## Sources

- [data.gov.my — Flood Warning API](https://developer.data.gov.my/realtime-api/flood-warning)
- [data.gov.my — Weather API](https://developer.data.gov.my/realtime-api/weather)
- [Open-Meteo — Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
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
