# Flood-Ready Township

Flood-Ready Township tells residents which street is about to flash-flood, when, and why. It sends the warning to their phones and asks them afterwards whether the water really came. It is built for Bandar Bukit Raja (BBR), a Sime Darby Property township in Klang, and runs on open data only.

Our entry for the [Sime Darby Property University Hackathon 2026](https://www.simedarbyproperty.com/universityhackathon), Township of Tomorrow, Planet track: climate resilience.

| | |
| --- | --- |
| Resident app | https://floodready-bbr.pages.dev |
| Admin app (SDP township team, login required) | https://floodready-admin.pages.dev |
| Pitch deck and demo video | links added at submission (23 Oct 2026) |

The apps are hosted on Cloudflare Pages. The API behind them runs on a team laptop and is reached through Tailscale Funnel, so the apps show data only while that laptop is on.

## The problem

BBR residents say Phase 1 and 2, especially Jalan Makyong, have flash-flooded at least three times a year since December 2021. In May 2024 their residents' council handed a memorandum to the Selangor Menteri Besar asking for retention ponds and bigger drains ([Sinar Harian, 25 May 2024](https://www.sinarharian.com.my/article/666626/edisi/selangor-kl/penduduk-bandar-bukit-raja-hadap-banjir-kilat-tiga-kali-setahun)).

Public warnings can't tell a resident which street will flood. JPS publishes river levels and rainfall per station, and MET Malaysia issues warnings per district. Selangor's fire and rescue department says some hotspots flood after only one to two hours of rain ([Kosmo](https://www.kosmo.com.my/?p=229246)), so people usually find out from social media or from the water itself. Nobody records which streets actually flooded and after how much rain, so drainage upgrades are argued from complaints instead of data.

## What we built

**Resident app** (installable PWA, Bahasa Melayu and English)
- A map of the township's 943 streets, each coloured Normal, Watch, Warning or Danger.
- A street page with the expected flood window, the reasons in plain words ("61.5 mm of rain in 1 h at Kg. Perepat, Kapar"), the river level and the tide.
- Push notifications for the streets you pick.
- A one-tap "Is it flooding here?" answer, with an optional photo. Answers confirm or reject each alert, and the street's alert history shows the outcome.

**Admin app** (for the SDP township team)
- A live operations map, plus street detail.
- Statistics and a monthly report built from every alert since January 2024.
- Street improvement suggestions, such as the streets with the most Warning and Danger episodes, or a gauge that has stopped sending valid data.
- A review queue for residents' answers and photos.
- A replay control that plays a real past flood through the system for training and demos.

**Engine** (Python)
- Reads JPS Public Infobanjir every 15 minutes: river levels and rain gauges for Selangor and Kuala Lumpur. It also reads MET Malaysia warnings, the Open-Meteo forecast and the Port Klang tide.
- Checks every reading for faults before using it.
- Turns readings into a level for each street. Each street uses its own river station and the rain gauges within 10 km, combined with a terrain-based flood susceptibility score from 1 to 5.
- Issues alerts, all-clears and a 6 to 24 hour outlook.

## What happened on 12 Nov 2024, replayed

That morning, seven Klang roads flooded 0.1 to 0.4 m deep, including Persiaran Sungai Keramat and Persiaran Batu Belah, two roads whose drains the residents' memorandum asked to enlarge ([RTM](https://berita.rtm.gov.my/nasional/senarai-berita-nasional/senarai-artikel/banjir-kilat-tujuh-laluan-di-klang-dinaiki-air/)). Replaying JPS's own 15-minute readings through the system gives this:

| Time | What the system did |
| --- | --- |
| 08:45 | 320 streets go to Watch: "45 mm of rain in 1 h at Kg. Perepat, Kapar". |
| 09:00 | 227 streets go to Warning: "61.5 mm of rain in 1 h at Kg. Perepat, Kapar". |
| 09:30 | Sungai Binjai at Pekan Meru crosses its 4.0 m warning level. |
| 10:00 | 323 streets go to Danger: "River at Sg. Binjai di Pekan Meru is 4.21 m, above its danger level (4.20 m)". |

So the first street alerts went out 45 minutes before the river crossed its warning level, and the first Warnings 30 minutes before.

![Rain and river level at Pekan Meru on 12 Nov 2024](docs/figures/eda/07_event_2024-11-12.png)

The replay runs in the Admin app and with `scripts/demo_replay.py`. Everything it creates is labelled Replay and left out of the statistics.

## What we measured, including what didn't work

Every number below comes from the full JPS archive (79 river stations and 233 rain gauges, January 2024 to October 2026). The evidence for each is in [docs/findings.md](docs/findings.md).

- **Our machine-learning model does not raise alerts, because it failed the test we set for it.** Before the final run we wrote down a bar: the model may raise a street to Watch only if it adds at least 30 minutes of warning, at no more than 1.5 times the false alarms, on stations it has never seen.
  - On inland rivers it passed. The JPS rules alone caught 795 of 890 river crossings with a median 90 minutes' warning. Rules plus the model caught 823 with 135 minutes, at 1.21 times the false alarms.
  - On 49 stations the model had never seen, it added only 15 minutes. So the official JPS thresholds set every level, and the model's probability is shown beside them for information. We kept the bar where it was. ([evaluation report](docs/evaluation-report.md))
- **Some public gauges are dead, and the data doesn't say so.** The river gauge at Kg. Perepat (`26558`) has been frozen since July 2024 and is still published as a live reading. Through about 60 storms it moved at most 0.08 m, while the river at Pekan Meru rose. Our quality checks found it and five other dead river gauges, and a rain gauge that reported 2,113 mm in one month. Across the archive they blank 193,723 river readings, but never one at or above an alert level. The 85 BBR streets that rely on Kg. Perepat use the nearest working river station instead, and the app says so.
- **Gridded rain misses flash floods.** On 12 Nov 2024, eight gridded rain sources showed at most 6.8 mm where the JPS gauge recorded 79 mm, so the system uses station rain only.
- **Near the coast, a high river is usually the tide.** At the two tidal stations, Bandar Klang and Pandamaran, nearly every warning-level crossing comes within 1.5 hours of high tide, often with no rain at all. Inland flash floods and spring tides are judged separately.
- **The terrain map points at the right streets.** 48 of the 61 street segments named in the residents' memorandum fall in the top two of five susceptibility classes, where chance would put 40%. The segments are not independent (38 of them are on Jalan Makyong), so we treat this as a check, not a score.
- **We limited notifications so people keep listening.** In April 2024, a stormy month, the busiest street would have received 65 alerts. We now push Watch at most once per street every 12 hours and always push Warning and Danger, which brings that street down to 30. Every alert is still shown in the app.

## How it works

```text
JPS Infobanjir · MET Malaysia · Open-Meteo · OpenStreetMap · FABDEM terrain
        │  loggers every 15 min, history archive, street and terrain builders
        ▼
quality checks  →  station features  →  JPS rules (+ ML probability, shown only)
        │
        ▼
street level (risk matrix: trigger × terrain susceptibility)  →  alerts, all-clears, outlook
        │  FastAPI + SQLite, Web Push
        ▼
Resident app (PWA)          Admin app
        ▲                        │
        └──── residents' answers confirm or reject alerts ────┘
```

Stack: Python 3.12 (pandas, scikit-learn, FastAPI, SQLAlchemy), React with Vite, TypeScript and react-leaflet, a pnpm workspace, and Web Push with VAPID keys. Python and web tests run in CI on every pull request; the Python suite has 820 tests.

## Run it locally

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node 22.

```bash
# Backend
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev,gis,ml,api]"   # .venv/bin/python on macOS and Linux
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/serve_api.py                                # API docs at http://localhost:8000/docs

# Web apps
npx pnpm@9.15.0 install
npx pnpm@9.15.0 dev:resident                                                 # http://localhost:5173
npx pnpm@9.15.0 dev:admin                                                    # http://localhost:5174

# Replay the 12 Nov 2024 flood (with the API running)
.venv/Scripts/python.exe scripts/demo_replay.py --event 2024-11-12 --speed 120
.venv/Scripts/python.exe scripts/demo_replay.py --stop                       # back to live
```

The tests and app builds work on a fresh clone. The API also needs the JPS archive, the live logs and the station lookup, which are not in git because of their size (about 830 MB). [HANDOFF.md §5](HANDOFF.md#5-data-and-running-processes) shows how to rebuild them.

To point your local apps at a running API instead, create `apps/resident/.env.local` or `apps/admin/.env.local` containing `VITE_API_URL=<the API's address>`.

Hosting step by step: [docs/hosting.md](docs/hosting.md). Starting everything after the laptop was off: [docs/runbook.md](docs/runbook.md).

## Repository

| Path | What |
| --- | --- |
| `floodready/` | Python package: data clients, quality checks, `engine/` (features, rules, risk matrix, alerts, replay), `ml/`, `gis/`, `api/`, `stats/` |
| `scripts/` | One runnable script per job: loggers, archive, builders, training, backfill, replay, admin accounts |
| `config/` | Townships, data sources, alert rules, risk matrix and ML settings (YAML) |
| `apps/resident/`, `apps/admin/` | The two web apps |
| `packages/shared/` | API types, mocks and level colours shared by both apps |
| `assets/geo/` | Generated street GeoJSON and street-to-station mapping |
| `models/` | Trained models |
| `tests/` | Python tests, with real-data fixtures |
| `docs/` | Product requirements, API contract, evaluation reports, findings, hosting guide ([index](docs/README.md)) |

## Limits

- The water-level sensor is simulated (`scripts/sim_sensor.py`). A real ESP32 unit is planned after the Top 10.
- Warnings start when rain reaches a gauge. On storms like 12 Nov 2024, that caps the lead time at about 90 minutes. A MET radar nowcast would see storms earlier, but MET's terms need written consent, so it is built and switched off.
- The MVP API runs on one laptop. systemd units for a VPS are in `deploy/` for later.
- News reports of past floods are not checked yet, so only residents' answers confirm alerts today.

## Team

Filbert (backend, ML, integration), Michael (backend), Darrell (frontend, UI/UX), Christian (frontend), Chingiz (DevOps, frontend).

## Data credits and licence

© OpenStreetMap contributors · JPS Public Infobanjir · MET Malaysia (via data.gov.my) · Open-Meteo (CC BY 4.0) · Terrain: Copernicus GLO-30, FABDEM (© University of Bristol, CC BY-NC-SA 4.0, non-commercial), ESA WorldCover 2021 (CC BY 4.0).

The code is licensed under the [Apache License 2.0](LICENSE). Data and data-derived files keep their own licences and are not covered by it. Street geometry in `assets/geo/` is from OpenStreetMap (ODbL), and its susceptibility columns derive from FABDEM (CC BY-NC-SA 4.0, non-commercial, share-alike); see [assets/geo/NOTICE.md](assets/geo/NOTICE.md). JPS, MET Malaysia and Open-Meteo data are used under their providers' terms and are not redistributed here.
