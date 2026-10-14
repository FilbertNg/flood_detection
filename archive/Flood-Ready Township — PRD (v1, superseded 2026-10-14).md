# Flood-Ready Township — Product Requirements Document

Oct 14, 2026 · @Filbert

## Overview

Flood-Ready Township predicts flash floods street by street, hours before they happen, and alerts residents through the SDP App. It is our entry for the [Sime Darby Property University Hackathon 2026](https://www.simedarbyproperty.com/universityhackathon) ("Township of Tomorrow"), **Planet track → Climate resilience**.

The system combines three things: a one-time **flood susceptibility map** (where water collects), a live **trigger model** (when it will flood, refreshed every 15 minutes from open rainfall, river-level, forecast and warning data), and **one physical water-level sensor** that confirms the prediction on the ground. Outputs are a resident alert, an SDP operations dashboard, and a flood-risk card for the sales gallery.

**Why SDP should care:** 78% of Malaysian buyers weigh climate risk when buying, with floods a top concern. A township that can prove its streets are monitored and low-risk gives buyers a reason to choose SDP.

| Milestone | Date |
| --- | --- |
| Registration closes | 21 Oct 2026 |
| Proposal submission | 23 Oct 2026 |
| Top 10 announced | 28 Oct 2026 |
| Mentoring sprint | 2–6 Nov 2026 |
| Final submission | 11 Nov 2026 |
| Top 10 pitch day | 14 Nov 2026 |
| Final presentation & awards | 3 Dec 2026 |

## Problem statement

SDP's own Bandar Bukit Raja residents say parts of their township flash-flood at least three times a year, and today's public warnings cannot tell them which street, or when.

**It is happening in an SDP township.** In May 2024 the Bandar Bukit Raja residents' council handed a memorandum to the Selangor Menteri Besar. They said Phase 1 and 2, especially Jalan Makyong, had flash-flooded at least three times a year since December 2021, with water reaching kitchens and living rooms of homes worth over RM500,000. They asked **Sime Darby Property**, the Klang city council and JPS to add retention ponds at Jalan Makyong and Jalan Sumazau, and to enlarge drains along Persiaran Sungai Keramat and Persiaran Batu Belah ([Sinar Harian, 25 May 2024](https://www.sinarharian.com.my/article/666626/edisi/selangor-kl/penduduk-bandar-bukit-raja-hadap-banjir-kilat-tiga-kali-setahun)).

**A typical event (4 June 2023).** More than three hours of heavy rain met a high tide. The Kampung Perepat (Kapar) telemetry station logged 98.5 mm, and Sungai Binjai at Pekan Meru rose to 4.38 m, above its 4.2 m danger level, at noon. About 50–100 homes in Pekan Meru, Bandar Baru Bukit Raja and Mutiara Bukit Raja flooded 0.1–0.5 m deep ([Sinar Harian / Bernama, 6 Jun 2023](https://www.sinarharian.com.my/article/262088/berita/semasa/rancangan-tebatan-banjir-di-klang-dilaksana-segera---nik-nazmi)).

**Why current warnings fall short.**

- JPS telemetry watches **rivers**, not housing-estate streets; its flood API reports river levels and rainfall per station ([data.gov.my](https://developer.data.gov.my/realtime-api/flood-warning)).
- Flash floods hit fast: Selangor Bomba says some hotspots flood after only 1–2 hours of rain ([Kosmo](https://www.kosmo.com.my/?p=229246)).
- Residents learn about floods from social media or rising water, not a timed, street-level alert.

**Why it matters commercially.** Experts say floods can erode property values by around 30% and buyers avoid "red zones" ([Bernama](https://bernama.com/en/news.php?id=2141696)). 78% of Malaysians weigh climate risk when buying ([PropertyGuru H1 2026](https://theiskandarian.com/propertyguru-sustainability-climate-risk-and-liveability-now-shape-how-malaysians-think-about-home/)).

**Problem statement:** *How might SDP give every resident a street-level flash-flood warning early enough to act, and give buyers proof their street is monitored, using only open data and minimal hardware?*

## Goals, non-goals and success metrics

The MVP must prove one thing: open data can warn an SDP street about a flash flood early enough for residents to act.

**Goals**

1. Give residents a street-level flood warning with an **Outlook** (6–24 h ahead) and a **Nowcast** (0–2 h ahead).
2. Give SDP a live map of flood risk across one pilot township.
3. Give the sales team a credible, data-backed flood-risk score per street.
4. Show the whole system working end to end on a replay of a real past flood.

**Non-goals (MVP)**

- No hydraulic or drain-network modelling.
- No dense sensor network; one physical sensor only.
- No integration with the real SDP App; we build a stand-in screen and a Telegram bot.
- No official warning role; JPS/MET/NADMA remain the authority.

**Success metrics (measured on held-out past events)**

| Metric | MVP target | How measured |
| --- | --- | --- |
| Event detection (recall) | ≥ 70% of known flood events flagged Warning or higher | Replay of held-out events |
| Nowcast lead time | Median ≥ 30 min before first report | Alert time vs news / Bomba report time |
| Outlook lead time | Median ≥ 6 h before first report | Same |
| False alarms | ≤ 4 Warning alerts per month with no flood | Count over logged/replayed months |
| Map match | ≥ 60% of known hotspots fall in risk 4–5 cells | Hotspot points vs susceptibility map |
| Pipeline freshness | Data ≤ 20 min old | Ingest timestamps |

Targets are starting assumptions for the pitch; we will report the real numbers we get.

## Users and personas

Four users share one data pipeline; residents and SDP ops are the MVP priority.

| Persona | Who | Main need | What they get | MVP priority |
| --- | --- | --- | --- | --- |
| Resident | Homeowner or tenant in an SDP township (e.g. Bandar Bukit Raja Phase 1) | Know early if *my street* will flood, so I can move my car and lift belongings | Outlook + Nowcast alert with street name, expected time, and what to do | Must |
| SDP township ops | SDP township management / facilities team | See where risk is rising across the township and act (clear drains, deploy staff, inform residents) | Live risk map, alert log, sensor status | Must |
| SDP sales team + buyer | Sales gallery staff and prospective buyers | Credible answer to "does this street flood?" | Street flood-risk card (1–5) with evidence and "monitored 24/7" badge | Should |
| Council (read-only) | MBDK / MBSA engineers | Street-level data they do not have today | Read-only dashboard view | Could |

## Solution overview

Street flood risk is the product of a fixed *where* score and a live *when* score, confirmed on the ground by one sensor.

```latex
\text{Risk}(street, t) = \text{Susceptibility}(street) \times P(\text{flood} \mid \text{weather}(t))
```

1. **Susceptibility map (where).** Built once per township on a 30 m grid from ground height (DEM), terrain features (slope, HAND, TWI, flow accumulation), distance to rivers, and hard surfaces. Trained on known flood locations (JPS/Bomba hotspots, news reports, Sentinel-1 flood extent). Output: score 1–5 per cell, rolled up per street.
2. **Trigger model (when).** Every 15 minutes it reads observed rain at nearby JPS stations, the nearest river level and trend against its danger threshold, the next 1–12 h rain forecast, MET warnings, and the last 3 days of rain. Output: probability of flooding in the next 1 h, 3 h and 6 h.
3. **Physical sensor (confirm).** One ESP32 + waterproof ultrasonic sensor over a drain (or a demo container) reports water level via MQTT. A sensor rise marks an alert as *confirmed* and becomes new training data.

**Two alert horizons**

| Alert | Lead time | Driven by | Confidence | Resident message (example) |
| --- | --- | --- | --- | --- |
| Outlook | 6–24 h | Rain forecast + MET warning + susceptibility | Medium | "High flash-flood risk in Bukit Raja Phase 1 this evening. Park on higher ground tonight." |
| Nowcast | 0–2 h | Observed rain + river trend + susceptibility (+ sensor) | High | "Flooding likely at Jalan Makyong in \~45 min. Move your car now." |

**Alert levels per street:** Normal → Watch → Warning → Danger, mirroring JPS's four river levels so residents and authorities read them the same way.

## Functional requirements

The MVP needs 18 Must requirements across six modules; Should and Could items are cut first if time runs short.

| ID | Module | Requirement | Priority |
| --- | --- | --- | --- |
| ING-1 | Ingestion | Poll data.gov.my Flood Warning API every 15 min for all stations within 25 km of the pilot township; store every reading with timestamp | Must |
| ING-2 | Ingestion | Poll data.gov.my Weather Warning API every 15 min; store warnings for the township's district | Must |
| ING-3 | Ingestion | Fetch Open-Meteo hourly forecast (precipitation, precipitation probability) for the township centroid every hour | Must |
| ING-4 | Ingestion | Receive sensor readings via MQTT (≤ 1 per minute) and store with device ID | Must |
| ING-5 | Ingestion | Flag readings of -9999 or station\_status OFF as missing; never treat them as zero | Must |
| MAP-1 | Susceptibility | Compute terrain features per 30 m cell from DEM (elevation, slope, HAND, TWI, flow accumulation, distance to river) | Must |
| MAP-2 | Susceptibility | Train a classifier on labelled flood / non-flood points and output a 1–5 score per cell | Must |
| MAP-3 | Susceptibility | Roll cell scores up to each OSM street segment (max and mean) | Must |
| MAP-4 | Susceptibility | Overlay Sentinel-1 December 2021 flood extent for validation | Should |
| TRG-1 | Trigger | Build features every 15 min: rain 1 h / 3 h / 6 h / 24 h / 72 h, river level vs danger level, river trend, forecast rain next 1/3/6/12 h, MET warning flag, hour of day | Must |
| TRG-2 | Trigger | Rule-based baseline model with tunable thresholds | Must |
| TRG-3 | Trigger | ML model (XGBoost) outputting P(flood) for next 1 h, 3 h, 6 h | Should |
| TRG-4 | Trigger | Combine with susceptibility into a street level (Normal / Watch / Warning / Danger) | Must |
| ALR-1 | Alerts | Send Telegram alert to subscribed residents when their street reaches Warning or Danger, with street, expected time, and action | Must |
| ALR-2 | Alerts | Send Outlook message when 6–24 h risk is high | Must |
| ALR-3 | Alerts | No repeat alert for the same street within 60 min unless the level rises | Must |
| ALR-4 | Alerts | Mark alert "confirmed" when the sensor rises above its threshold | Should |
| UI-1 | Ops dashboard | Map of streets coloured by level, station markers, sensor marker, alert log | Must |
| UI-2 | Ops dashboard | Time-series chart per station/sensor (rain, river level, sensor level) | Must |
| UI-3 | Resident view | Mobile screen mimicking an SDP App tab: my street status, forecast, alert history | Must |
| UI-4 | Sales card | Per-street card: risk score, past events near the street, "monitored" badge | Should |
| DEM-1 | Demo | Replay mode: run the full pipeline over a past event (e.g. 4 Jun 2023) at accelerated speed | Must |
| DEM-2 | Demo | Evaluation report: recall, lead time, false alarms on held-out events | Should |
| ADM-1 | Admin | Council read-only login | Could |

## Data sources and ML approach

All inputs are open data; the full schema and scraping plan live in the companion doc, *Flood-Ready Township — Training Data Spec*.

| Data | Source | Used for | Notes |
| --- | --- | --- | --- |
| River level, rainfall per station (15 min) | [data.gov.my Flood Warning API](https://developer.data.gov.my/realtime-api/flood-warning) (JPS) | Trigger, live | Includes normal/alert/warning/danger levels and trend; real-time only, so we log it ourselves |
| Weather warnings, 7-day forecast | [data.gov.my Weather API](https://developer.data.gov.my/realtime-api/weather) (MET) | Trigger | Warnings by area |
| Hourly rain forecast | [Open-Meteo](https://open-meteo.com/en/docs) | Outlook | Free tier is non-commercial |
| Historical hourly rain | [Open-Meteo archive (ERA5 / ERA5-Land)](https://open-meteo.com/en/docs/historical-weather-api) | Training | ERA5-Land \~11 km, from 1950 |
| Ground height | Copernicus GLO-30 DEM / FABDEM | Susceptibility | 30 m |
| Streets, rivers, buildings | OpenStreetMap | Susceptibility, street roll-up |  |
| Land cover | ESA WorldCover 10 m | Susceptibility | Impervious share |
| Flood labels | JPS/Bomba hotspot lists, news reports, Sentinel-1 | Training + validation | Hand-checked |

**Models**

- **Susceptibility:** Random Forest / XGBoost classifier on DEM-derived features, an approach used for flash-flood mapping in published studies ([ISPRS 2022](https://isprs-archives.copernicus.org/articles/XLVI-4-W3-2021/305/2022/)).
- **Trigger:** rule baseline first, then XGBoost on event-day vs normal-rainy-day examples. Split train/test by event date, never randomly.
- **Explainability:** every alert shows its top drivers (e.g. "62 mm in 3 h at Kg Perepat + Sg Binjai rising").

## System architecture and tech stack

Live feeds pass through one ingest layer into a database; the trigger model and the susceptibility map meet in a single street-level score that every screen reads.

&#91;embedded content: system architecture · 5 sources, 2 models, 4 outputs\]

The GIS path runs once per township; everything else refreshes every 15 minutes. All outputs read the street level through one FastAPI service.

| Layer | Choice | Why |
| --- | --- | --- |
| Ingest | Python + APScheduler (or cron) | Simple 15 min polling jobs |
| Sensor | ESP32 + waterproof ultrasonic sensor, Mosquitto MQTT | Cheap, well documented |
| Storage | PostgreSQL + PostGIS (SQLite acceptable for MVP) | Time series + street geometry in one place |
| GIS | rasterio, WhiteboxTools or pysheds, GeoPandas | HAND, TWI, flow accumulation without hydrology expertise |
| Satellite | Google Earth Engine (Sentinel-1) | Free flood-extent mapping |
| ML | scikit-learn, XGBoost | Fast to train, explainable feature importance |
| API | FastAPI | One service for all screens |
| Frontend | React + Leaflet (or Streamlit for speed) | Map-first UI |
| Alerts | Telegram Bot API | Free push stand-in for SDP App |

## User flows and screens

Three screens cover the MVP; each is a web view we can later embed in the real SDP App.

**Resident flow**

1. Resident joins the Telegram bot (stand-in for SDP App push) and picks their street.
2. Outlook arrives the day before or that afternoon when 6–24 h risk is high.
3. Nowcast arrives when the street hits Warning: street name, expected time, top reason, action ("Move your car to \[nearest higher car park set by SDP ops\]").
4. "Confirmed" follow-up if the sensor rises; "All clear" when the level drops back to Normal.
5. Resident can open the status screen any time: my street level, next 12 h rain, last 5 alerts.

**SDP ops flow**

1. Dashboard map shows every street coloured by level, JPS stations, and the sensor.
2. Ops clicks a red street → sees drivers, rain and river charts, alert history.
3. Ops posts a manual note (e.g. "drain cleared") that is attached to the event log.

**Sales gallery flow**

1. Agent searches a street or unit.
2. Card shows risk score 1–5, nearest recorded flood events with dates and sources, and the "monitored 24/7" badge.
3. Buyer can scan a QR code to open the same card on their phone.

**Screen list**

| Screen | User | Key elements |
| --- | --- | --- |
| Resident status | Resident | Street level badge, 12 h rain bar chart, alert history, "what to do" tips |
| Alert message | Resident | Level, street, ETA, top driver, action, link to status |
| Ops map | SDP ops | Street layer, stations, sensor, filter by level, replay slider |
| Ops detail | SDP ops | Rain / river / sensor charts, drivers, notes |
| Sales card | Sales + buyer | Score, evidence list, badge, QR |

## Non-functional requirements

The system must be fresh, honest about uncertainty, and safe with resident data.

| Area | Requirement |
| --- | --- |
| Freshness | Live inputs ≤ 20 min old; alert sent ≤ 2 min after a level change |
| Availability | Ingest jobs retry 3× with backoff; a missing source degrades the level confidence, never silently drops to Normal |
| Rate limits | Respect data.gov.my limits (Weather API: 4 requests/min without token, 10 with); request a token from dataterbuka@jdn.gov.my |
| Transparency | Every alert shows its data time and top drivers; a footer says JPS/MET/NADMA remain the official source |
| Privacy (PDPA) | Store only Telegram chat ID + chosen street; no home address or phone number; delete on unsubscribe |
| Licensing | Open-Meteo free tier is non-commercial → fine for hackathon; production needs a paid plan or MET data. Credit OpenStreetMap (ODbL) and Copernicus data on screens |
| Reproducibility | All data pulls and model training run from scripts in the repo; raw files are versioned with a date stamp |
| Cost | MVP runs on a free-tier VM or a laptop; sensor built from low-cost hobby parts (ESP32 + waterproof ultrasonic sensor); exact bill of materials to be priced |

## Business case

Flood-Ready Township turns a known SDP pain point into a selling point: "the only township that warns you street by street."

**Why buyers choose SDP**

- 78% of Malaysians consider climate risk when buying, with flooding and landslides the key concerns ([PropertyGuru H1 2026](https://theiskandarian.com/propertyguru-sustainability-climate-risk-and-liveability-now-shape-how-malaysians-think-about-home/)).
- Official flood hazard maps still have limited public access in Malaysia ([EdgeProp](https://www.edgeprop.my/content/1916824/flood-risk-does-not-always-sink-property-values)), so a developer that publishes street-level risk stands out.
- Floods hurt resale: Taman Sri Muda prices fell 14.3% after the 2021 flood vs 6.1% in nearby non-flooded areas ([EdgeProp](https://www.edgeprop.my/content/1910792/)).

**Value to SDP**

| Value | How |
| --- | --- |
| Sales | "Flood-monitored" badge and street risk card in the sales gallery |
| Trust | Answers residents' public complaints (Bandar Bukit Raja memorandum) with action, not only statements |
| Operations | Ops team sees where to clear drains and deploy staff before an event |
| Planning | Event history guides platform levels and retention pond sizing in later phases |
| Scale | One pipeline covers all SDP townships; each new township needs only its DEM run and optional sensors |

**Cost model (MVP → pilot)**

| Item | MVP | Pilot (1 township) |
| --- | --- | --- |
| Data | Free open data | Same + paid forecast API if used commercially |
| Compute | Laptop / free-tier VM | Small cloud VM + database |
| Sensors | 1 hobby unit | A handful of industrial units at known hotspots |
| Alerts | Telegram bot | SDP App push notifications |

Exact pilot costs will be quoted with SDP during mentoring.

## Risks, assumptions and mitigations

The biggest risk is too few labelled flood events; every other risk has a cheaper fallback.

| Risk / assumption | Impact | Mitigation |
| --- | --- | --- |
| Few labelled events at street level | Weak trigger model | Combine news, Bomba, JPS hotspot and Sentinel-1 labels; widen to all of Klang/Petaling districts; rule baseline as fallback |
| Historical JPS readings not available via API | No station history for training | Use Open-Meteo ERA5 for history; start logging the live API now; quote station values reported in news (e.g. Kg Perepat 98.5 mm) |
| ERA5 rain is coarse (\~11–25 km) and smooths thunderstorms | Under-predicts short intense bursts | Use it for training only; live system uses station rain; report this limit openly |
| Thunderstorm forecasts are uncertain | Outlook false alarms | Outlook is labelled medium confidence; Warning needs observed rain |
| Tide affects coastal Klang floods (4 Jun 2023, 12 Nov 2024 coincided with high tides) | Missed driver | Add tide height feature if time allows (Should) |
| DEM resolution (30 m) misses drains and kerbs | Street score noise | Roll up per street, validate against hotspots, never claim house-level accuracy |
| News locations are vague | Label noise | Geocode to street or taman level only; manual check of every positive label |
| Alert fatigue | Residents ignore alerts | 60 min cooldown; two horizons; track false-alarm rate |
| Liability | Resident relies on us instead of authorities | Footer: advisory only; JPS/MET/NADMA are official |

## Timeline, milestones and team

The proposal on 23 Oct needs design and data, not models; the working demo is due 11 Nov.

**By 21 Oct — register**

- [ ] Team of 3–5 registered with at least one coder

**By 23 Oct — proposal**

- [ ] Live API logger running (data.gov.my flood + weather, every 15 min)
- [ ] Pilot township chosen (Bandar Bukit Raja) and bounding box fixed
- [ ] First labelled events table (≥ 5 events near SDP townships)
- [ ] Architecture diagram and screen mock-ups
- [ ] Proposal written against the six judging criteria

**24 Oct – 1 Nov — data and map**

- [ ] DEM features + susceptibility model + street roll-up
- [ ] Historical rain pulled for all labelled events and negatives
- [ ] Rule-based trigger working on replay

**2–6 Nov — mentoring sprint**

- [ ] XGBoost trigger + evaluation report
- [ ] Sensor node streaming over MQTT
- [ ] Ask SDP mentors: drain specs, past incident dates, pilot township preference

**7–11 Nov — final build**

- [ ] Dashboard, resident screen, sales card, Telegram bot
- [ ] Replay demo of 4 Jun 2023 end to end
- [ ] Final submission

**14 Nov — Top 10 pitch** · **3 Dec — final presentation**

| Role | Owns |
| --- | --- |
| Data engineer | API loggers, Open-Meteo pulls, news scraping, database |
| GIS / ML 1 | DEM features, susceptibility model, street roll-up |
| ML 2 | Trigger model, evaluation |
| Backend + IoT | FastAPI, Telegram bot, ESP32 sensor, MQTT |
| Frontend + pitch | Dashboard, resident screen, sales card, slides, buyer survey |

## Demo script and evaluation plan

The pitch replays a real Bandar Bukit Raja flood and shows the alert landing before the water.

**3-minute demo**

1. **(30 s) Problem:** Bandar Bukit Raja residents' memorandum; floods at Jalan Makyong ≥ 3 times a year.
2. **(30 s) Map:** susceptibility map of the township; red streets match the memorandum streets and past reports.
3. **(60 s) Replay 4 Jun 2023:** Outlook turns orange the evening before (if the forecast supports it); Nowcast turns Jalan Makyong red as Kg Perepat rain climbs and Sg Binjai rises toward 4.2 m; Telegram alert fires on stage.
4. **(30 s) Live sensor:** pour water under the sensor; dashboard marks the alert "confirmed".
5. **(30 s) Sales card + business case:** "Jalan X — risk 2/5, monitored 24/7"; buyer survey result; pilot ask.

**Evaluation plan**

- Hold out at least 3 events (one per year) that the model never trains on.
- Report recall, median lead time vs first report, false alarms per month, and hotspot map match (targets in Goals).
- Show one failure honestly and what data would fix it.
- Run a 30–50 person buyer survey: "Would a flood-monitored street make you choose this home? How much more would you pay?"

## Sources

- [SDP University Hackathon 2026 — official page](https://www.simedarbyproperty.com/universityhackathon)
- [Sinar Harian — Bandar Bukit Raja residents face flash floods three times a year (25 May 2024)](https://www.sinarharian.com.my/article/666626/edisi/selangor-kl/penduduk-bandar-bukit-raja-hadap-banjir-kilat-tiga-kali-setahun)
- [Sinar Harian / Bernama — Klang flood mitigation, 4 Jun 2023 event (6 Jun 2023)](https://www.sinarharian.com.my/article/262088/berita/semasa/rancangan-tebatan-banjir-di-klang-dilaksana-segera---nik-nazmi)
- [Utusan — Flash floods in Selangor, 12 Nov 2024 (13 Nov 2024)](https://www.utusan.com.my/berita/2024/11/hujan-lebat-luar-biasa-punca-banjir-kilat-di-selangor-semalam/)
- [RTM — Seven roads in Klang flooded incl. Persiaran Sungai Keramat (12 Nov 2024)](https://berita.rtm.gov.my/nasional/senarai-berita-nasional/senarai-artikel/banjir-kilat-tujuh-laluan-di-klang-dinaiki-air/)
- [data.gov.my — Flood Warning API](https://developer.data.gov.my/realtime-api/flood-warning)
- [data.gov.my — Weather API](https://developer.data.gov.my/realtime-api/weather)
- [Open-Meteo — Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [Kosmo — Bomba Selangor flash-flood hotspots](https://www.kosmo.com.my/?p=229246)
- [Bernama — Floods erode property value by 30%](https://bernama.com/en/news.php?id=2141696)
- [The Iskandarian — PropertyGuru H1 2026 study](https://theiskandarian.com/propertyguru-sustainability-climate-risk-and-liveability-now-shape-how-malaysians-think-about-home/)
- [EdgeProp — Flood risk and property values](https://www.edgeprop.my/content/1916824/flood-risk-does-not-always-sink-property-values)
- [EdgeProp — Taman Sri Muda price impact](https://www.edgeprop.my/content/1910792/)
- [ISPRS — ML flash-flood susceptibility, Tetouan](https://isprs-archives.copernicus.org/articles/XLVI-4-W3-2021/305/2022/)
