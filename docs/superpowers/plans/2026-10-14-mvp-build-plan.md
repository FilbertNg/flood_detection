# Flood-Ready Township — MVP Build Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> This is the **master plan** for five people. It fixes the shared contracts, the work order and each task's files, interfaces and acceptance tests. When you pick up a task, have your Claude Code expand **that task** into bite-sized TDD steps with superpowers:writing-plans (save the plan as `docs/superpowers/plans/<date>-<task-id>.md`), then execute it. Never change a contract in §4 without the PR rule in §9.

**Goal:** a working MVP on GitHub by **23 Oct 2026, 11:59 pm**: Resident PWA + SDP Admin app + an **ML-first flood engine** (JPS rules as a safety floor) running on real JPS data, shown in a 5-minute video and a 10-slide deck.

**Architecture:**
- A Python engine turns JPS station readings, tide and a street susceptibility map into street flood levels, alerts, time windows and reasons. Its trigger is **ML-first**: a gradient-boosted classifier, trained on 2024–2026 JPS data pooled across all river stations, gives the probability that the river near each township crosses its warning level within 1–2 h. JPS's official rain and river thresholds act as a **safety floor** (the level is the higher of the two). Evidence: `docs/ml-feasibility.md`. It runs every 15 min in live mode, at accelerated speed in replay mode, and over 2024–2026 history in backfill mode.
- A FastAPI service exposes it to two React + Leaflet apps and sends Web Push.
- MVP hosting costs $0: GitHub Actions cron for the 15-min tick, a free Postgres, Cloudflare Pages for the apps. A VPS comes only after Top 10.

**Tech Stack:**
- **Python 3.12:** pandas, pyarrow, scikit-learn + joblib (ML trigger), SQLAlchemy 2 Core, FastAPI, pywebpush, PyJWT, pysheds/rasterio/geopandas (GIS only).
- **TypeScript:** React + Vite, react-leaflet, TanStack Query, Recharts, vite-plugin-pwa, MSW, Vitest; pnpm workspaces.
- **Hosting:** GitHub Actions, Supabase Postgres (free), Cloudflare Pages.

## 1. What we submit on 23 Oct

| Component | Required | What ours is | Owner |
| --- | --- | --- | --- |
| Pitch deck | Yes, ≤ 10 main slides + appendix | Story → product → evidence (real JPS replay, backtest) → business → ask | Darrell (design), Filbert (content) |
| Video / demo link | Yes, 5 min | Screen recording: 12 Nov 2024 replay → phone push → verify → admin stats/suggestions; plus live mode | Darrell + Christian |
| Prototype / code | Yes | This public GitHub repo, with README + setup + deployed app links | Everyone; Chingiz owns the release |
| Supporting documents | Optional | PRD, evaluation report, Plan Review | Filbert |

**The MVP is done when the video can show, on real data and nothing faked:**
1. **Resident app** (phone, installed PWA):
   - pick a street;
   - map of street levels;
   - street page with level, **ML flood probability**, time window, reasons and 12 h rain;
   - a push notification arrives during the replay;
   - "Is it flooding here?" Yes/No; "Report a flood".
2. **Admin app:**
   - login;
   - live ops map;
   - street detail charts;
   - statistics, monthly report and improvement suggestions computed from the **2024–2026 backfill** (rules run over the archived JPS history, outcomes matched to news reports).
3. **Live mode:** current levels from today's JPS data, refreshed every 15 min.
4. **Simulated water-level sensor**, labelled "simulated" on screen. Hardware comes after Top 10.

## 2. Global constraints

- **No fabricated data anywhere.** Replay data is archived JPS data. Backfill outcomes come from news or real resident answers. Anything simulated is marked `is_simulated` / `is_replay` / `source='demo'` in the DB and labelled on screen. Statistics exclude replay and demo rows.
- **Levels:** exactly `normal`, `watch`, `warning`, `danger` (lowercase in JSON). Python `floodready.engine.types.Level(IntEnum)`: NORMAL=0, WATCH=1, WARNING=2, DANGER=3.
- **IDs:** `street_id` = `<TOWNSHIP_ID>-<slug of street name>`, e.g. `BBR-jalan-makyong`; `township_id` from `config/townships.yaml` (`BBR`, `USJ`, `ELMINA`, …); `graph_id` = Infobanjir station id (`26558`, `PEKANMERU`).
- **Time:** all times are Malaysia time (MYT, UTC+8), ISO 8601 with offset in the API (`2024-11-12T09:00:00+08:00`), naive MYT inside the engine.
- **Station rules (starting values, `config/rules.yaml`):**
  - rain: Watch at `st_rain_1h ≥ 31` mm or `st_rain_2to4h_max ≥ 40` mm; Warning at `st_rain_1h > 60` mm or `st_rain_2to4h_max ≥ 60` mm;
  - river: alert → Watch, warning → Warning, danger → Danger (the station's own thresholds).
- **ML-first trigger with a rule floor (`config/ml.yaml`):** trigger level = max(ML level, rule level). ML level from the model probability: Watch at `p ≥ p_watch`, Warning at `p ≥ p_warning` (chosen on validation folds only; spike values 0.5 / 0.7). ML may raise a level, never lower one. ML drives alert levels only while `ml_drives_alerts: true`, set by the evaluation gate (task ML3); otherwise the probability is still shown but the rules decide.
- **Risk matrix (`config/risk_matrix.yaml`), susceptibility 1–5 × trigger level → street level:**

| Susceptibility | normal | watch | warning | danger |
| --- | --- | --- | --- | --- |
| 1 | normal | normal | normal | watch |
| 2 | normal | normal | watch | watch |
| 3 | normal | watch | watch | warning |
| 4 | normal | watch | warning | danger |
| 5 | normal | watch | warning | danger |

- **Alerts:** issued when a street reaches `warning` or `danger`; no repeat for a street within 60 min unless the level rises; an "all clear" message when it returns to `normal`.
- **Nowcast time window:** `issued_at + 30 min` to `issued_at + 90 min` (`config/rules.yaml`, tuned on events).
- **Languages:** Resident app and push text in BM and English; Admin app in English.
- **Privacy:** residents have no account (random `device_id`); location rounded to 3 decimals (~100 m); photo EXIF stripped; no names, phone numbers or addresses.
- **Credits on every map:** © OpenStreetMap contributors · Data: JPS Public Infobanjir, MET Malaysia, Open-Meteo.
- **Footer on every alert and street page:** "Advisory only. JPS, MET and NADMA are the official sources."
- **Tests:** TDD; `pytest` for Python, `vitest` for TypeScript. CI must pass before merge.

## 3. MVP architecture (no VPS, no hardware)

```text
GitHub Actions cron */15 ──► scripts/tick.py ──► ingest JPS + MET + forecast ──► engine ──► Postgres (Supabase free)
                                                                        └──► Web Push (VAPID) to subscribers
FastAPI (free host, or local + tunnel for the demo) ◄──► Postgres
   ├── /api/v1/...  public (resident) + admin (JWT)
   └── replay runner (12 Nov 2024 from archived JPS data, accelerated) ──► Web Push
Cloudflare Pages: apps/resident (PWA), apps/admin  ──► FastAPI
Laptop logger (already running) = backup copy of live data (parquet)
```

- **Dev and test DB:** SQLite (SQLAlchemy Core, portable types). **Prod DB:** Supabase Postgres.
- **Mocks:** both apps start against MSW mocks built from §4 examples, so frontend work never waits for the backend.
- **After Top 10:** move to the VPS (`deploy/`), add the ESP32 sensor and the Cloudflare watchdog.

## 4. Contracts (frozen at M0; change only via §9)

### 4.1 File structure

```text
floodready/                  # Python package (exists: infobanjir, met, openmeteo, http, storage, jobs)
  engine/
    types.py                 # Level, Reason, TriggerResult, StreetState, Alert (dataclasses)
    features.py              # station features from 15-min readings
    rules.py                 # station + township trigger levels
    matrix.py                # risk matrix lookup
    levels.py                # street states: level, window, reasons
    alerts.py                # alert issuing with cooldown / all-clear
    replay.py                # replay clock + runner over archived readings
    backfill.py              # run engine over 2024-2026 history
  gis/
    streets.py               # OSM streets for a township → named streets GeoJSON
    terrain.py               # DEM → HAND, TWI → baseline index → street susceptibility
  tide.py                    # hourly tide series for Port Klang
  ml/
    dataset.py               # pooled training table: station-relative features + crossing labels
    train.py                 # fit, save artifact + model card
    evaluate.py              # event-level metrics vs rule baselines, gate decision
    predict.py               # load artifact; probability per township at time t
  db/
    schema.py                # SQLAlchemy Core tables (§4.3)
    repo.py                  # read/write functions used by API, tick, replay
  api/
    main.py                  # FastAPI app factory
    public.py                # resident endpoints
    admin.py                 # admin endpoints (JWT)
    auth.py
  push.py                    # Web Push send + VAPID
  stats/
    outcomes.py              # alert outcomes from answers / news
    statistics.py            # admin statistics
    report.py                # monthly report JSON
    suggestions.py           # SUG-1..7
scripts/                     # run_loggers, archive_jps_history, rebuild_jps_history (exist) + tick, replay, backfill, build_streets, build_susceptibility, sim_sensor, seed_admin
config/                      # townships.yaml, sources.yaml (exist) + rules.yaml, risk_matrix.yaml, ml.yaml
models/                      # trigger_v<N>.joblib + model card trigger_v<N>.md (committed if < 10 MB)
notebooks/spikes/            # exploration (ml_trigger_feasibility.py)
assets/geo/                  # bbr_streets.geojson (generated, committed; ODbL attribution)
data/events/events.csv       # human-checked flood labels (committed; facts + URLs only)
apps/resident/               # Vite + React + TS PWA
apps/admin/                  # Vite + React + TS
packages/shared/             # TS: api types + client, map components, level colours, i18n, MSW mocks
.github/workflows/           # ci.yml, tick.yml
docs/api-contract.md         # §4.2 as a living document
```

### 4.2 API (base `/api/v1`)

> **After F1 the source of truth is [`docs/api-contract.md`](../../api-contract.md) + `packages/shared/src/api/types.ts`** (mocks in `packages/shared/src/mocks/index.ts`). The table and examples below are a summary.

| Method + path | Auth | Returns / accepts |
| --- | --- | --- |
| `GET /status` | — | `{mode: "live"\|"replay", now: ts, data_time: ts, replay: {event, speed}\|null, sources: {jps_wl_stale: int, jps_rf_stale: int}}` |
| `GET /streets?township=BBR` | — | GeoJSON FeatureCollection; `properties: {street_id, name, township_id, susceptibility: 1-5, level, updated_at}` |
| `GET /streets/{street_id}` | — | `StreetDetail` (below) |
| `GET /stations?township=BBR` | — | `[{graph_id, name, kind: "rf"\|"wl", lat, lon, latest: {time, rain_1h_mm\|wl_m}, thresholds: {alert, warning, danger}\|null, is_stale}]` |
| `GET /stations/{graph_id}/series?from&to` | — | `[{time, rain_15min_mm, wl_m}]` |
| `GET /alerts?street_id&active=true` | — | `[AlertSummary]` |
| `GET /push/public-key` | — | `{key: string}` (VAPID public key) |
| `POST /subscriptions` | — | in: `{device_id, subscription: PushSubscriptionJSON, street_ids: string[], lang: "en"\|"ms"}` → `204` |
| `DELETE /subscriptions/{device_id}` | — | `204`; deletes all data for the device |
| `POST /answers` | — | multipart: `device_id, street_id, alert_id?, answer: yes\|no\|not_sure\|report, depth?: ankle\|knee\|above_knee, lat?, lon?, photo?` → `{answer_id}`; 409 if the device already answered this alert |
| `POST /sensor/readings` | sensor token | `{device_id, level_cm, simulated: bool}` → `204` |
| `POST /admin/login` | — | `{email, password}` → `{token}` |
| `GET /admin/stats?from&to` | JWT | `Stats` (below) |
| `GET /admin/report?month=YYYY-MM` | JWT | `Report` (below) |
| `GET /admin/suggestions?from&to` | JWT | `[Suggestion]` |
| `PATCH /admin/suggestions/{id}` | JWT | `{status: open\|accepted\|dismissed\|done, note?}` |
| `GET /admin/answers?review_status=pending` | JWT | `[Answer]`; `PATCH /admin/answers/{id}` `{review_status: valid\|spam}` |
| `POST /admin/notes` | JWT | `{street_id, text}` |
| `POST /admin/replay` / `DELETE /admin/replay` | JWT | `{event: "2024-11-12", speed: 60}` → starts / stops replay |

```jsonc
// StreetDetail
{
  "street_id": "BBR-jalan-makyong", "name": "Jalan Makyong", "township_id": "BBR",
  "susceptibility": 5, "level": "warning", "trigger_level": "warning",
  "confidence": "high",                         // high | medium (outlook) | low (stale data)
  "flood_probability": 0.62,                    // ML trigger, 0-1; null if the model is unavailable
  "fired_by": ["rule_rain"],                    // rule_rain | rule_river | model | outlook
  "window": {"start": "2024-11-12T09:30:00+08:00", "end": "2024-11-12T10:30:00+08:00"},
  "reasons": [
    {"code": "rain_1h", "value": 61.5, "unit": "mm", "station": "Kg. Perepat, Kapar",
     "text": {"en": "61.5 mm of rain in 1 h at Kg. Perepat, Kapar", "ms": "Hujan 61.5 mm dalam 1 jam di Kg. Perepat, Kapar"}},
    {"code": "ml_probability", "value": 0.62, "unit": "p", "station": "Sg. Binjai di Pekan Meru",
     "text": {"en": "62% chance the river at Sg. Binjai di Pekan Meru crosses warning level within 2 h",
              "ms": "62% kemungkinan paras Sg. Binjai di Pekan Meru melepasi paras amaran dalam 2 jam"}}
  ],
  "data_time": "2024-11-12T09:00:00+08:00",
  "rain_next_12h": [{"time": "2024-11-12T10:00:00+08:00", "mm": 2.1}],
  "tide": [{"time": "2024-11-12T10:00:00+08:00", "height_m": 1.9}],
  "river_forecast": {"graph_id": "PEKANMERU", "points": [{"time": "2024-11-12T10:00:00+08:00", "wl_m": 4.05, "wl_m_p90": 4.25}]},  // Should (ML5); null if unavailable
  "stations": ["26558", "PEKANMERU"],
  "active_alert": {"alert_id": "a_01", "level": "warning", "issued_at": "2024-11-12T09:00:00+08:00"},
  "history": [{"alert_id": "a_01", "street_id": "BBR-jalan-makyong", "horizon": "nowcast", "kind": "alert", "level": "warning",
               "issued_at": "…", "window": {"start": "…", "end": "…"}, "outcome": "unverified", "is_replay": true}],   // AlertSummary
  "is_replay": true
}
// Stats
{
  "period": {"from": "2024-01-01", "to": "2026-10-14"},
  "kpis": {"alerts": 0, "confirmed": 0, "not_confirmed": 0, "unverified": 0,
           "confirmation_rate": 0.0, "missed_floods": 0, "median_lead_min": null},
  "by_week": [{"week": "2024-W46", "alerts": 0, "confirmed": 0}],
  "by_street": [{"street_id": "…", "name": "…", "alerts": 0, "confirmed": 0, "floods": 0}],
  "rain_at_onset": [{"street_id": "…", "event_date": "2024-11-12", "rain_2to4h_mm": 79.0}],
  "station_health": [{"graph_id": "26558", "name": "…", "stale_pct": 0.0}],
  "sources": {"outcomes_from_news": 0, "outcomes_from_residents": 0}
}
// Report = {"month": "2024-11", "summary": {...Stats.kpis}, "events": [...], "top_streets": [...], "suggestions": [Suggestion], "data_health": [...]}
// Suggestion
{"id": "s_01", "street_id": "…", "street_name": "…", "rule": "SUG-1", "priority": "high",
 "text": "Jalan Makyong needs a drainage capacity review: it floods with less rain than the JPS 60 mm guide.",
 "evidence": {"flood_dates": ["2024-11-12"], "rain_at_onset_mm": [45.0], "notes": "…"},
 "status": "open", "note": null}
```

### 4.3 Database tables (SQLAlchemy Core, `floodready/db/schema.py`)

`stations(graph_id, kind, name, district, state, lat, lon, wl_alert_m, wl_warning_m, wl_danger_m)` ·
`readings(graph_id, kind, time_local, rain_15min_mm, wl_m, source, fetched_at)` PK (graph_id, kind, time_local) ·
`streets(street_id, township_id, name, susceptibility, centroid_lat, centroid_lon, geometry_geojson)` ·
`street_state(street_id, mode, level, trigger_level, confidence, flood_probability, fired_by_json, window_start, window_end, reasons_json, data_time, updated_at)` PK (street_id, mode) ·
`alerts(alert_id, street_id, township_id, horizon, level, kind ['alert'|'all_clear'], issued_at, window_start, window_end, fired_by_json, reasons_json, inputs_json, recipients, is_replay, is_backfill)` ·
`answers(answer_id, device_id, alert_id, street_id, answer, depth, photo_path, lat3, lon3, distance_m, answered_at, review_status, source ['resident'|'news'|'demo'])` ·
`subscriptions(device_id, endpoint, p256dh, auth, lang, created_at)` · `subscription_streets(device_id, street_id)` ·
`sensor_readings(device_id, time_local, level_cm, simulated)` ·
`suggestions(id, street_id, rule, priority, text, evidence_json, status, note, period_from, period_to, created_at)` ·
`ops_notes(id, street_id, text, author, created_at)` · `admin_users(email, password_hash, role)`

### 4.4 Engine interfaces (`floodready/engine`)

```python
class Level(IntEnum): NORMAL = 0; WATCH = 1; WARNING = 2; DANGER = 3

@dataclass(frozen=True)
class Reason:  code: str; value: float; unit: str; station: str | None; text_en: str; text_ms: str

@dataclass(frozen=True)
class TriggerResult:  level: Level; confidence: str; fired_by: tuple[str, ...]; reasons: tuple[Reason, ...]; data_time: datetime; stale_stations: tuple[str, ...]

@dataclass(frozen=True)
@dataclass(frozen=True)
class MLResult:  p: float; level: Level; station: str; horizon_h: int; reasons: tuple[Reason, ...]

@dataclass(frozen=True)
class StreetState:  street_id: str; level: Level; trigger_level: Level; confidence: str; flood_probability: float | None; fired_by: tuple[str, ...]
                    window_start: datetime | None; window_end: datetime | None; reasons: tuple[Reason, ...]; data_time: datetime

@dataclass(frozen=True)
class Alert:  street_id: str; level: Level; kind: str; issued_at: datetime; window_start: datetime | None; window_end: datetime | None; reasons: tuple[Reason, ...]; fired_by: tuple[str, ...]

features.station_features(readings: pd.DataFrame, at: datetime, stations: pd.DataFrame) -> pd.DataFrame
    # readings cols: graph_id, kind, time_local, rain_15min_mm, wl_m ; stations cols: graph_id, kind, name, wl_alert_m, wl_warning_m, wl_danger_m
    # returns one row per (graph_id, kind): st_rain_1h, st_rain_2to4h_max, st_rain_24h, wl_m, river_band ('normal'|'alert'|'warning'|'danger'|None), river_rising, is_stale
rules.township_trigger(features: pd.DataFrame, station_ids: list[str], cfg: dict) -> TriggerResult
ml.predict.township_probability(model, features: pd.DataFrame, wl_station_ids: list[str], at: datetime, cfg: dict) -> MLResult
levels.combine(rule: TriggerResult, ml: MLResult | None, cfg: dict) -> TriggerResult   # max(rule, ML); rules only if ml is None or ml_drives_alerts is false
matrix.street_level(susceptibility: int, trigger: Level, table: dict) -> Level
levels.street_states(streets: pd.DataFrame, trigger: TriggerResult, cfg: dict) -> list[StreetState]
alerts.issue(prev: dict[str, StreetState], new: list[StreetState], last_alerts: dict[str, Alert], cfg: dict) -> list[Alert]   # last alert or all-clear per street (its level is needed for "unless the level rises")
replay.run(event_start: datetime, event_end: datetime, step: timedelta, readings: pd.DataFrame, ...) -> Iterator[tuple[datetime, list[StreetState], list[Alert]]]
```

## 5. Team and ownership

| Person | Role | Owns |
| --- | --- | --- |
| **Filbert** | Backend + AI/ML, integration lead | **ML trigger** (dataset, training, evaluation gate, inference), engine (features, rules floor, matrix, levels, alerts, replay, backfill), GIS susceptibility, tide, labels + evaluation report, suggestions engine; merges contract changes |
| **Michael** | Backend | DB layer, FastAPI (public + admin + auth), Web Push, answers/outcomes, statistics/report endpoints, tick script, sensor endpoint + simulator |
| **Darrell** | Frontend + UI/UX | Design system and screens for both apps, **Admin app** lead, deck design, video edit |
| **Christian** | Frontend | **Resident app**: PWA, map, street page, verify/report, push subscription, BM/EN |
| **Chingiz** | DevOps + frontend | Monorepo + CI + branch protection, GitHub Actions tick, Supabase, hosting (Pages + API), secrets, `packages/shared` map components; then Admin statistics pages with Darrell |

Everyone reviews one teammate's PRs. Filbert and Michael review each other's backend PRs; Darrell, Christian and Chingiz rotate on frontend PRs.

## 6. Work order (dependencies, not dates)

Start every task as soon as its dependencies are merged. Frontends depend only on M0 contracts and mocks.

| Milestone | Done when | Unblocks |
| --- | --- | --- |
| **M0 Foundations** | Contracts merged (§4 as files), monorepo builds in CI, DB schema + SQLite dev DB, design tokens, MSW mocks | Everyone works in parallel |
| **M1 Engine replay (headless)** | `python scripts/replay.py --event 2024-11-12` prints the BBR timeline from real data: Watch 08:45, Warning 09:00, Danger 10:00 | API real data, deck evidence slide |
| **M2 Vertical slice** | Resident app on a phone shows replay levels from the real API, and a push arrives | Video storyboard can be recorded |
| **M3 Full MVP** | ML trigger trained, gated and integrated (or shown as probability if it fails the gate); verify/report, Admin stats/report/suggestions on backfill, live tick in Actions, simulated sensor, BM/EN, deployed links | Freeze |
| **M4 Ship** | Feature freeze → bug bash on Android + iPhone → video + deck final → submission checklist (§11) | Submit |

**Rule of thumb:** freeze features with at least 36 h left before the deadline, and submit at least 6 h early.

## 7. Tasks

Each task lists: **Owner · Depends on · Files · Interfaces · Acceptance tests · Done when**. Acceptance tests are the minimum; write them first.

### Workstream F — Foundations (M0)

#### F1. Contracts as code
**Owner:** Michael + Filbert · **Depends:** — · **Files:** create `docs/api-contract.md` (§4.2 verbatim), `floodready/engine/types.py` (§4.4 dataclasses), `config/rules.yaml`, `config/risk_matrix.yaml` (§2 values), `packages/shared/src/api/types.ts` (TS mirrors of StreetDetail, Stats, Report, Suggestion, AlertSummary, Station, Answer), `packages/shared/src/mocks/index.ts` (one typed example per endpoint; TypeScript rather than JSON so `tsc` checks every mock against the types)
- **Acceptance:** `tests/engine/test_types.py::test_levels_order` (`Level.DANGER > Level.WARNING > Level.WATCH > Level.NORMAL`); `test_risk_matrix_config_complete` (5 × 4 entries, all valid level names); a TS type check (`pnpm -C packages/shared tsc --noEmit`) passes with the mocks typed as the interfaces.
- **Done when:** merged; announced in the team chat; from now on contract changes follow §9.
- **Status:** implemented on branch `feat/contracts-f1` (also adds `config/ml.yaml`, level-name parity test between Python and TypeScript, and a "Mock data" ribbon rule for the apps).

#### F2. Monorepo, CI and branch protection
**Owner:** Chingiz · **Depends:** — · **Files:** `package.json` + `pnpm-workspace.yaml` (apps/*, packages/*), `apps/resident` and `apps/admin` (Vite React TS templates), `packages/shared` (TS lib), `.github/workflows/ci.yml` (jobs: `python` = pip install `-e .[dev]` + `pytest -q`; `web` = `pnpm i --frozen-lockfile` + `pnpm -r lint` + `pnpm -r test` + `pnpm -r build`), `.nvmrc`, `README.md` (add web commands)
- **Acceptance:** CI green on a PR; each app renders "Flood-Ready" at `/` with a Vitest smoke test; `main` protected: PR required, 1 approval, CI required, no force push.
- **Done when:** a teammate can `pnpm i && pnpm -C apps/resident dev` from a fresh clone.

#### F3. Database layer
**Owner:** Michael · **Depends:** F1 · **Files:** `floodready/db/schema.py` (§4.3), `floodready/db/repo.py`, `scripts/db_init.py`, `tests/db/test_repo.py`; add deps `sqlalchemy>=2`, `psycopg[binary]` to `pyproject.toml`
- **Interfaces produced:** `repo.connect(url) -> Engine`; `repo.upsert_readings(conn, df)`; `repo.load_readings(conn, graph_ids, start, end) -> DataFrame`; `repo.save_street_states(conn, states, mode)`; `repo.get_street_states(conn, township, mode)`; `repo.insert_alerts(conn, alerts, is_replay, is_backfill) -> list[str]`; `repo.insert_answer(...)`; `repo.list_subscribers(conn, street_id) -> list[Subscription]`.
- **Acceptance:** with SQLite in-memory: upserting the same readings twice keeps one row; `save_street_states` then `get_street_states` round-trips all fields; `insert_answer` twice for the same (device_id, alert_id) raises `DuplicateAnswer`.
- **Done when:** `python scripts/db_init.py --url sqlite:///data/dev.db` creates all tables, and `--url $DATABASE_URL` works on Supabase.

#### F4. Design system and screen designs
**Owner:** Darrell · **Depends:** — · **Files:** `packages/shared/src/theme/tokens.ts` (colours incl. the 4 level colours with text contrast ≥ 4.5:1, spacing, type scale), `packages/shared/src/components/LevelBadge.tsx`, `docs/design/` (screen designs for every screen in PRD "User flows and screens", as images or Figma link)
- **Acceptance:** Vitest: `LevelBadge` renders the localized label for each level; level colours readable in light and dark mode.
- **Done when:** Christian and Darrell build screens from it.

### Workstream E — Engine (Filbert) → M1

#### E1. Real-data fixtures for the engine
**Depends:** PR #1 merged + `scripts/rebuild_jps_history.py --kind rf` after the archive finishes · **Files:** `scripts/make_engine_fixtures.py`, `tests/fixtures/engine/bbr_20241112_readings.csv` (26558 rf + PEKANMERU wl, 2024-11-11 00:00 → 2024-11-12 23:45), `tests/fixtures/engine/stations.csv`
- **Acceptance:** fixture contains 26558 rain 14.0 at 08:30, 31.0 at 08:45, 16.5 at 09:00, 0.0 at 08:15; PEKANMERU 3.81 at 09:15, 4.06 at 09:30, 4.21 at 10:00, thresholds 3.80 / 4.00 / 4.20.

#### E2. Station features
**Depends:** E1, F1 · **Files:** `floodready/engine/features.py`, `tests/engine/test_features.py`
- **Acceptance (real data):** at 2024-11-12 08:45, 26558 `st_rain_1h == 45.0`; at 09:00 `== 61.5`; PEKANMERU at 09:30 `river_band == "warning"`, `river_rising is True`; at 10:00 `river_band == "danger"`; a station with no reading for > 2 h before `at` → `is_stale is True`; a missing quarter (None) is not counted as 0 in sums and is reported in a `n_missing_1h` column.

#### E3. Rules → township trigger
**Depends:** E2 · **Files:** `floodready/engine/rules.py`, `tests/engine/test_rules.py`
- **Acceptance:** BBR trigger with stations [26558, PEKANMERU]: 08:30 → NORMAL; 08:45 → WATCH with reason `rain_1h` 45.0 at "Kg. Perepat, Kapar"; 09:00 → WARNING, `fired_by == ("rule_rain",)`; 09:30 → WARNING, `fired_by` contains both `rule_rain` and `rule_river`; 10:00 → DANGER with reason `river_level` 4.21 at "Sg. Binjai di Pekan Meru"; all stations stale → confidence `low` and level not lowered to NORMAL silently (reason `stale_data`).

#### E4. Risk matrix, street states, time window, reasons
**Depends:** E3, G2 (or a stub streets table) · **Files:** `floodready/engine/matrix.py`, `floodready/engine/levels.py`, `tests/engine/test_levels.py`
- **Acceptance:** matrix examples from §2 (S5+WARNING→WARNING, S2+WARNING→WATCH, S1+WATCH→NORMAL, S4+DANGER→DANGER); a street with susceptibility 5 at 09:00 → level WARNING, window 09:30–10:30, reasons[0].text_en `"61.5 mm of rain in 1 h at Kg. Perepat, Kapar"`, text_ms `"Hujan 61.5 mm dalam 1 jam di Kg. Perepat, Kapar"`; reasons ranked by how far each value is past its threshold.

#### E5. Alerts with cooldown and all-clear
**Depends:** E4 · **Files:** `floodready/engine/alerts.py`, `tests/engine/test_alerts.py`
- **Acceptance:** WARNING at 09:00 → alert; WARNING again at 09:15 → none (cooldown); DANGER at 10:00 → new alert (level rose); back to NORMAL → one `all_clear`; WATCH never produces an alert.

#### E6. Replay runner + CLI (M1)
**Depends:** E5, F3 · **Files:** `floodready/engine/replay.py`, `scripts/replay.py`, `tests/engine/test_replay.py`
- **Acceptance:** replaying 2024-11-12 06:00–14:00 at 15-min steps yields the trigger timeline Watch 08:45 → Warning 09:00 → Danger 10:00; with `--db` it writes `street_state(mode='replay')` and alerts with `is_replay=1`; CLI prints one line per change.
- **Done when (M1):** `python scripts/replay.py --event 2024-11-12` prints the timeline, shown in the team chat.

#### E7. Backfill 2024–2026
**Depends:** E6, L1 · **Files:** `floodready/engine/backfill.py`, `scripts/backfill.py`, `tests/engine/test_backfill.py`
- **Acceptance:** over the fixture day it produces the same alerts as replay, flagged `is_backfill=1`; ML probabilities in the backfill are **out-of-fold** (each period scored by the ML2 model that did not train on it), so Admin statistics are not inflated; on the full archive it completes for BBR, USJ and ELMINA and prints alert counts per township per month.

#### E8. Outlook (6–24 h)
**Depends:** E4, existing forecast + MET logs · **Files:** `floodready/engine/outlook.py`, `floodready/met_parse.py`, `tests/engine/test_outlook.py`
- **Logic:** township Outlook = WATCH-level `outlook` alert (confidence `medium`) when an active MET land thunderstorm / heavy-rain warning names Selangor or the township's district, **or** the forecast sum for the next 6–24 h ≥ 40 mm (`config/rules.yaml`). The window is the forecast peak-rain hours. Reasons cite the warning title or the forecast amount, and say that forecasts often miss tropical storms.
- **Acceptance:** the saved MET fixture text naming Selangor → `met_warning_active` true for BBR; a forecast with 45 mm over 18:00–21:00 → outlook window 18:00–21:00; no warning and 5 mm forecast → no outlook; outlook alerts obey the same 60 min cooldown.

### Workstream G — Geography (Filbert, with Claude)

#### G1. Streets for BBR
**Depends:** — · **Files:** `floodready/gis/streets.py`, `scripts/build_streets.py`, `assets/geo/bbr_streets.geojson`, `tests/gis/test_streets.py`; add `geopandas`, `shapely` to an optional `gis` extra
- **Acceptance:** OSM highways inside a 3 km buffer of the BBR centre; segments merged by name into named streets; unnamed service roads dropped; `street_id` slugs unique; Jalan Makyong and Persiaran Sungai Keramat present.

#### G2. Susceptibility baseline (HAND + TWI)
**Depends:** G1 · **Files:** `floodready/gis/terrain.py`, `scripts/build_susceptibility.py`, `tests/gis/test_terrain.py`, updates `assets/geo/bbr_streets.geojson` (`susceptibility` 1–5, `hand_m_min`, `twi_max`)
- **Data:** FABDEM tile for 3°N 101°E if downloadable quickly, otherwise Copernicus GLO-30 tile `Copernicus_DSM_COG_10_N03_00_E101_00_DEM` from the public AWS bucket `copernicus-dem-30m`.
- **Acceptance:** on a synthetic 5 × 5 DEM with a valley, the valley cells get the highest index; every BBR street has a 1–5 score; `scripts/build_susceptibility.py` prints where the memorandum streets fall, whatever the result. The baseline uses no flood labels, so it is a fair out-of-sample check.

#### G3. Tide
**Depends:** — · **Files:** `floodready/tide.py`, `scripts/build_tide.py`, `tests/test_tide.py`
- **Method:** Open-Meteo Marine `sea_level_height_msl` at an offshore point near Port Klang (≈ 2.95, 101.25) for history + 7 days ahead; fall back to utide on JUPEM table values.
- **Acceptance:** series is hourly, without gaps, for 2024-01 → +48 h; high water on 2024-11-12 is found within ±1 h of the JUPEM table time (recorded in the test).

### Workstream L — Labels and evaluation (Filbert, with Claude)

#### L1. Events table
**Files:** `data/events/events.csv` (schema from Data Spec Dataset 1), `scripts/news_search.py`, `scripts/extract_events.py`, `tests/test_events_schema.py`
- **Acceptance:** schema test (required columns, enums, `evidence_quote` and `source_url` non-empty, `checked_by` filled); contains the 6 seed incidents plus every Klang / Petaling / KL flash flood found for 2024-01 → today; no article text stored beyond the evidence quote.

#### L2. Evaluation report (supporting document)
**Depends:** E7, L1 · **Files:** `scripts/evaluate.py`, `docs/evaluation-report.md`
- **Contents:** the ML-vs-rules out-of-sample table and the gate decision (ML3); for every labelled 2024+ event: detected? first Watch/Warning time vs report time (lead); Warning days per township per month over the backfill (false-alarm ceiling); the gridded-vs-station rain gap (12 Nov 2024, 23 Apr 2025); one honest failure.

### Workstream ML — ML trigger (Filbert, with Claude) · Must

**Evidence:** `docs/ml-feasibility.md`. Sg. Binjai crossed warning 50 times in 2.5 years. A first classifier (no tide, 10 stations, no tuning) matched the Watch rule's detection with 90 vs 60 min median lead, but more false alarms. This workstream turns that into a pooled, tide-aware, gated model.
**Depends on:** archive finished + `scripts/rebuild_jps_history.py` (PR #1), G3 tide, station coordinates (old data.gov.my list: `station_code` usually equals the graph ID).

#### ML1. Pooled training dataset
**Depends:** archive + rebuild, G3 · **Files:** `floodready/ml/dataset.py`, `scripts/build_ml_dataset.py`, `tests/ml/test_dataset.py`, `config/ml.yaml`; add `scikit-learn`, `joblib` to `pyproject.toml`
- **Rows:** one per river station per quarter hour while the level is below that station's warning level; only stations whose thresholds are in order (normal < alert < warning < danger).
- **Labels:** `cross_1h`, `cross_2h` = the level reaches the station's warning level within the next 1 / 2 h.
- **Features (only data at or before t):**
  - level minus each threshold;
  - rises over 15 / 60 / 120 min;
  - rain sums 1 / 2 / 3 / 6 / 24 h and 72 h antecedent, as max and mean over rain stations within 10 km and within 25 km;
  - tide height and hours to high water (G3);
  - hour and month.
  - No station ID feature (the model must generalise, not memorise stations).
- **Acceptance (real data):** PEKANMERU at 2024-11-12 08:30 has `cross_2h == 1` (crosses at 09:30) and at 06:00 `cross_2h == 0`; rows at or above warning are excluded; **leakage test:** changing any value after t leaves every feature at t unchanged; stations with broken threshold order are excluded and listed in the build log.

#### ML2. Training and evaluation harness
**Depends:** ML1 · **Files:** `floodready/ml/train.py`, `floodready/ml/evaluate.py`, `scripts/train_trigger.py`, `tests/ml/test_evaluate.py`, `models/trigger_v1.joblib`, `models/trigger_v1.md` (model card: data range, features, folds, metrics, known limits)
- **Model:** `HistGradientBoostingClassifier(class_weight="balanced")`. Probability smoothed as the max over the last 30 min (the spike's probability was jumpy).
- **Validation:** time-blocked folds by season (4 folds, an event never split across folds); 12 Nov 2024 always in a test fold.
- **Event metrics** (spike definitions): crossings detected 15 min–3 h ahead, median lead, false-alarm episodes per month, per station and pooled, side by side with the Watch and Warning rain rules.
- **Acceptance:**
  - on a synthetic series, a fired window 60 min before a crossing counts as detected with lead 60, and an alarm with no crossing in the next 3 h counts as false;
  - on the spike configuration (PEKANMERU, same archive snapshot) the harness reproduces the Watch-rule baseline: 23 / 50 detected, 4.9 false alarms per month.

#### ML3. Gate and thresholds
**Depends:** ML2 · **Files:** `config/ml.yaml` (`p_watch`, `p_warning`, `smoothing_min`, `ml_drives_alerts`), the ML section of `docs/evaluation-report.md`
- Pick `p_watch` and `p_warning` on validation folds only.
- **Gate:** (a) detection ≥ the Watch rule with false alarms ≤ the Watch rule, **or** (b) equal detection with ≥ 20 min more median lead and ≤ 1.2× false alarms. Pass → `ml_drives_alerts: true`. Fail → `false`, and the report says so plainly.
- **Done when:** the out-of-sample rules-vs-ML table is in the evaluation report and on the deck's evaluation slide.

#### ML4. Inference in the engine
**Depends:** ML3, E4 · **Files:** `floodready/ml/predict.py`, `floodready/engine/levels.py` (`combine`), `tests/ml/test_predict.py`, `tests/engine/test_combine.py`
- **Township probability:** max over the township's named river stations (BBR: PEKANMERU, 26558, PANDAMARAN, SELATMUARA).
- **Acceptance:**
  - `combine` never returns a level below the rule level;
  - with `ml_drives_alerts: false`, levels equal rules-only while `flood_probability` is still filled;
  - reasons include `ml_probability` with BM / EN text;
  - the 12 Nov 2024 replay shows the probability at every step;
  - works in live, replay and backfill modes;
  - if the model can't be loaded, the engine falls back to rules-only with a confidence note, never a crash.

#### ML5 (Should). River level forecast curve
`HistGradientBoostingRegressor` with quantile loss (p50, p90) at 1 h and 2 h; served as `river_forecast` in StreetDetail; drawn as a dashed line on the Resident and Admin charts. **Acceptance:** p90 coverage between 0.85 and 0.95 on held-out folds.

#### ML6 (Should). Street flash-flood classifier
Supervised on news and resident labels (L1) at township-day level, using station and ML4 features. Ships only with ≥ 20 labelled events and if it improves on ML4 in leave-one-event-out evaluation; recall reported as "X of N".

#### ML7 (Should). ML susceptibility map
Random forest on the G2 terrain features with flood points, spatial block cross-validation; kept only if it beats the HAND + TWI baseline on held-out BBR streets.
### Workstream B — Backend API (Michael)

#### B1. App factory + public read endpoints
**Depends:** F1, F3 · **Files:** `floodready/api/main.py`, `floodready/api/public.py`, `tests/api/test_public.py`; add deps `fastapi`, `uvicorn`, `httpx` (tests)
- **Acceptance (TestClient + SQLite seeded from E6 replay):** `GET /streets?township=BBR` returns a FeatureCollection whose properties match §4.2; `GET /streets/BBR-jalan-makyong` matches the StreetDetail shape; `GET /status` reports `mode`; CORS allows the two app origins from env `CORS_ORIGINS`.

#### B2. Web Push
**Depends:** B1 · **Files:** `floodready/push.py`, `floodready/api/public.py` (subscriptions, public key), `scripts/gen_vapid.py`, `tests/test_push.py`; add `pywebpush`
- **Acceptance:** subscribing stores device + streets; `notify(alert)` sends only to subscribers of that street, in their language, with payload `{title, body, url: "/street/<id>", alert_id, level}`; a 404/410 from the push service deletes the subscription; `DELETE /subscriptions/{device_id}` removes everything for that device.

#### B3. Replay control
**Depends:** B2, E6 · **Files:** `floodready/api/admin.py` (replay endpoints), `floodready/api/replay_runner.py`
- **Acceptance:** `POST /admin/replay {event: "2024-11-12", speed: 60}` advances replay time 1 min per second, writes states, and sends push for replay alerts (marked `[Replay]` in the title); `GET /status` shows replay progress; `DELETE` stops it and returns to live mode.

#### B4. Answers, sensor, outcomes
**Depends:** B1 · **Files:** `floodready/api/public.py` (answers), `floodready/stats/outcomes.py`, `scripts/sim_sensor.py`, `tests/stats/test_outcomes.py`
- **Acceptance:** outcome rules from PRD "Live benchmark" (≥ 2 yes or 1 yes with photo → confirmed; ≥ 3 no and 0 yes → not_confirmed; else unverified; sensor above threshold → confirmed); news events from `events.csv` confirm backfill alerts with `source='news'`; a report with no alert in the previous 3 h is a missed flood; when an alert becomes confirmed, subscribers of that street get one "Confirmed by neighbours" push; `sim_sensor.py --curve rise` posts a rising series with `simulated=true`.

#### B5. Admin: auth, stats, report, suggestions endpoints
**Depends:** B4, S1 · **Files:** `floodready/api/auth.py`, `floodready/api/admin.py`, `floodready/stats/statistics.py`, `floodready/stats/report.py`, `scripts/seed_admin.py`, `tests/api/test_admin.py`; add `pyjwt`, `bcrypt`
- **Acceptance:** wrong password → 401; endpoints without a token → 401; `GET /admin/stats` on backfill data returns §4.2 Stats with replay/demo rows excluded; `GET /admin/report?month=2024-11` includes the 12 Nov 2024 event.

#### B6. Live tick
**Depends:** E5, B2 · **Files:** `scripts/tick.py`, `tests/test_tick.py`
- **Acceptance:** one tick = run loggers → upsert readings → compute live states → issue alerts → push; idempotent when run twice for the same 15-min slot (no duplicate alerts).

### Workstream S — Suggestions (Filbert)

#### S1. Suggestion rules SUG-1..7
**Depends:** E7, B4 (outcomes), G3 · **Files:** `floodready/stats/suggestions.py`, `tests/stats/test_suggestions.py`
- **Acceptance:** one synthetic case per rule triggers exactly that rule with its evidence (e.g. SUG-1: 3 confirmed floods with onset rain 35, 42, 48 mm → "drainage capacity review"); priorities as in the PRD; every suggestion text ends with "Screening suggestion; site survey needed."

### Workstream R — Resident app (Christian)

#### R1. App shell, PWA, i18n, API client
**Depends:** F2, F4 · **Files:** `apps/resident/src/main.tsx`, `src/routes/*`, `src/i18n/{en,ms}.json`, `vite.config.ts` (vite-plugin-pwa: manifest, icons, service worker), `packages/shared/src/api/client.ts`
- **Acceptance:** Vitest: language toggle switches strings; Lighthouse PWA "installable" passes on the built app; runs against MSW mocks with `VITE_USE_MOCKS=1`.

#### R2. Onboarding + home map
**Depends:** R1, F1 mocks · **Files:** `apps/resident/src/routes/Onboarding.tsx`, `src/routes/Home.tsx`, `packages/shared/src/map/StreetLayer.tsx` (with Chingiz)
- **Acceptance:** pick streets by search or map tap → stored in localStorage with a random `device_id`; map colours streets by level from `GET /streets`; my streets pinned; active-alert banner when any of my streets is at warning or above.

#### R3. Street page
**Depends:** R2 · **Files:** `apps/resident/src/routes/Street.tsx`, `src/components/{Reasons,RainChart,TideChart}.tsx`
- **Acceptance:** renders level badge, confidence, time window ("between 9:30 and 10:30"), reasons in the chosen language, 12 h rain bars, tide line, what-to-do tips, data time, official-source footer; shows "Replay" ribbon when `is_replay`.

#### R4. Push subscription + notification handling
**Depends:** R1, B2 (or mocks) · **Files:** `apps/resident/src/push/subscribe.ts`, `src/sw/notifications.ts`
- **Acceptance:** permission flow, then `POST /subscriptions`; clicking a notification opens `/street/<id>`; iPhone users who haven't installed the app see the "Add to Home Screen" guide; tested on Android Chrome and iOS Safari (installed PWA).

#### R5. Verify + report
**Depends:** R3, B4 (or mocks) · **Files:** `apps/resident/src/components/VerifySheet.tsx`, `src/routes/Report.tsx`
- **Acceptance:** Yes / No / Not sure + depth + optional photo + optional location, posted as multipart; a 409 shows "You already answered"; report form works with no active alert; photo removed from memory after upload.

### Workstream A — Admin app (Darrell lead, Chingiz)

#### A1. Shell, login, layout
**Depends:** F2, F4 · **Files:** `apps/admin/src/main.tsx`, `src/routes/Login.tsx`, `src/auth.ts`
- **Acceptance:** token stored in memory + sessionStorage; 401 → back to login; navigation: Map, Statistics, Reports, Suggestions, Review.

#### A2. Ops map + street detail
**Depends:** A1, shared map · **Files:** `apps/admin/src/routes/OpsMap.tsx`, `src/routes/StreetDetail.tsx`, `src/components/StationChart.tsx`
- **Acceptance:** streets by level, stations greyed when stale, answer pins; detail charts rain/river with threshold lines from `/stations/{id}/series`; ops note form; replay start/stop control.

#### A3. Statistics (Chingiz)
**Depends:** A1, B5 (or mocks) · **Files:** `apps/admin/src/routes/Statistics.tsx`, `src/components/{KpiTiles,ByWeekChart,ByStreetTable,RainAtOnsetChart}.tsx`
- **Acceptance:** period filter; KPI tiles; charts; a "data source" note showing news vs resident outcome counts.

#### A4. Report + suggestions
**Depends:** A1, B5 (or mocks) · **Files:** `apps/admin/src/routes/Report.tsx` (print stylesheet → PDF), `src/routes/Suggestions.tsx`
- **Acceptance:** month picker; print preview fits A4; suggestions ranked by priority with evidence and status buttons (PATCH).

### Workstream D — DevOps and hosting (Chingiz)

#### D1. Free Postgres + secrets
**Depends:** F3 · Create the Supabase project (free tier; verify current limits), run `scripts/db_init.py`, store `DATABASE_URL`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `JWT_SECRET`, `SENSOR_TOKEN` as GitHub Actions secrets and in the API host. Never commit `.env`.

#### D2. Tick in GitHub Actions
**Depends:** D1, B6 · **Files:** `.github/workflows/tick.yml` (`schedule: cron "*/15 * * * *"` + `workflow_dispatch`)
- **First check:** run the JPS live logger from a GitHub runner and confirm Infobanjir answers from outside Malaysia. If it is blocked, keep the tick on a teammate's always-on PC and use Actions only for the forecast and MET.
- **Acceptance:** 4 successful runs in a row; readings appear in Postgres; a failed run notifies the team (GitHub email is enough for MVP).

#### D3. Deploy API + apps
**Depends:** B1, R2, A1 · Apps on Cloudflare Pages (`VITE_API_URL`); API on a free host that runs a Docker or Python web service (verify cold-start time and limits); fallback: local API + Cloudflare quick tunnel for the live demo. HTTPS is required for PWA and push.
- **Acceptance:** both app URLs load on a phone; installing the Resident PWA works; push from the deployed API reaches the phone.

### Workstream P — Pitch (Darrell, Filbert; everyone reviews)

#### P1. Deck (≤ 10 slides + appendix)
**Depends:** M1 for the evidence slide · **Slides:**
1. Problem (memorandum)
2. Why current warnings fail
3. Solution (two apps + engine)
4. How it works (Mechanism): ML trigger + JPS safety floor
5. Evidence: 12 Nov 2024 replay from real JPS data
6. Evaluation: ML vs official rules, out-of-sample
7. Admin value: stats + suggestions
8. Enabler: tech, open data, scale to all SDP townships
9. Business case and cost
10. Team + ask

Appendix: data sources, gridded-vs-station finding, roadmap (sensor, VPS, SDP App).

#### P2. 5-minute video
**Depends:** M2 for storyboard, M3 for final · **Script:**
- 0:00 problem;
- 0:40 Resident app tour;
- 1:30 replay 12 Nov 2024 with phone push on screen;
- 2:45 verify + simulated sensor;
- 3:15 Admin stats, report, suggestions;
- 4:15 live mode on today's data;
- 4:40 impact + ask.

Record at 1080p with captions; upload unlisted on YouTube and link it in the README.

## 8. Definition of Done (every task)

- Tests written first and passing in CI; no skipped tests.
- Matches §4 contracts; UI copy in BM and English (Resident app).
- No secrets, no personal data, no fabricated data; simulated / replay data flagged and labelled.
- README or `docs/` updated if setup or usage changed.
- PR reviewed and approved by one teammate; squash-merged into `main`.

## 9. Git workflow

- Branch from `main`: `feat/<area>-<short>`, `fix/<area>-<short>`, `docs/…`, `ops/…` (area = engine, gis, api, push, resident, admin, shared, ci, pitch).
- Conventional commits (`feat(engine): …`). Small PRs (aim for ≤ 400 changed lines). Rebase on `main` before requesting review. Never force-push `main` or rewrite pushed shared history.
- **Contract changes** (§4 files, `packages/shared/src/api/types.ts`, `docs/api-contract.md`, DB schema) need a PR labelled `contract` and approval from **both** a backend and a frontend owner. Update the mocks in the same PR.
- PR template: what / why / how tested / screenshots for UI.

## 10. Scope guard (cut in this order if time runs short)

1. Street flash-flood classifier (ML6), ML susceptibility (ML7), river forecast curve (ML5).
2. Telegram fallback, review queue (ADM-7), sales card.
3. USJ and ELMINA backfill (keep BBR only).
4. Live deployment of the API (keep the local API + tunnel; the video is the required artifact).
5. Tide in reasons (keep it in the charts).

Never cut: the ML trigger with its honest out-of-sample evaluation (if it fails the gate it still ships as a displayed probability), the real-data replay, the Resident app push, verify, Admin statistics + suggestions from backfill, the video, the deck.

## 11. Submission checklist

- [ ] Deck PDF ≤ 10 main slides (+ appendix), file name `FloodReadyTownship_Deck.pdf`.
- [ ] Video ≤ 5 min, link works in a private browser window.
- [ ] GitHub repo public; README has: what it is, screenshots, video link, live links, setup in ≤ 5 commands, data credits.
- [ ] Supporting docs linked: PRD, evaluation report.
- [ ] A fresh clone passes CI; demo replay works offline.
- [ ] Submitted at least 6 h before 23 Oct 2026, 11:59 pm; confirmation screenshot in the team chat.

## 12. Risks specific to the build

| Risk | Mitigation |
| --- | --- |
| Infobanjir blocks GitHub runners (foreign IPs) | D2 first check; fallback: tick on a teammate's PC; JPS history backfills gaps |
| GitHub Actions cron runs late (5–15 min, sometimes more) | Fine for MVP; the demo uses replay |
| Free API host sleeps (cold start) | Warm it up before recording; local API + tunnel fallback |
| iPhone push needs the installed PWA (iOS 16.4+) | Install guide in onboarding; record the demo on Android if needed |
| Merge conflicts across 5 people | Contracts frozen at M0; small PRs; one owner per directory |
| ML trigger fails the gate | Ships as a displayed probability and forecast; rules decide alerts; reported honestly (judges value a fair comparison) |
| ML overfits or leaks future data | Time-blocked folds, leakage test (ML1), smoothing, model card with limits |
| Backfill has few news-confirmed outcomes | Show counts honestly ("confirmed by news: N"); verification loop is the long-term fix |
