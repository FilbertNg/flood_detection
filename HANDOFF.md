# Handoff — Flood-Ready Township

**As of 15 Oct 2026, 02:00 MYT** · Submission due **23 Oct 2026, 11:59 pm** (deck ≤ 10 slides, 5-min video, this repo)

This is the starting point for anyone (or any Claude Code session) picking up work. Read this, then [`CLAUDE.md`](CLAUDE.md) (rules) and the [build plan](docs/plans/2026-10-14-mvp-build-plan.md) (tasks and contracts). The folder map is in [README.md](README.md); every document is listed in [docs/README.md](docs/README.md).

## 1. Where we are

**The flood prediction works end to end on real data:** JPS readings → features → JPS rule floor + ML probability → street levels with time window and reasons → API → Resident app map and street page, in **live** mode (every 15 min) and **replay** mode (real past floods).

| Milestone | Status |
| --- | --- |
| M0 Foundations | Done: contracts, workspace, CI (Python + web on every PR), level theme. Design system still basic (F4) |
| M1 Engine replay | Done: `python scripts/replay.py --event 2024-11-12` |
| M2 Vertical slice | Mostly done: Resident app shows replay and live levels from the API. **Push notifications not yet** (B2/R4) |
| M3 Full MVP | Not started: verify/report, Admin app, statistics/suggestions, DB, deployment |
| M4 Ship | Not started: deck, video, submission |

Merged PRs: #1 rain fix · #2 build plan + PRD v3 · #4 contracts · #5 GIS + tide · #6 engine · #7 ML trigger · #8 API · #9 Resident app + CI. Tests: **119 Python, 5 Vitest**, all green in CI.

## 2. Run it (5 minutes)

```bash
# Python 3.12 + uv
uv venv .venv && uv pip install --python .venv/Scripts/python.exe -e ".[dev,gis,ml,api]"   # .venv/bin/python on macOS/Linux
.venv/Scripts/python.exe -m pytest -q

# Web (Node 22; pnpm via npx is fine)
npx pnpm@9.15.0 install

# Demo
.venv/Scripts/python.exe scripts/serve_api.py                                        # API → http://localhost:8000/docs
npx pnpm@9.15.0 dev:resident                                                         # app → http://localhost:5173
.venv/Scripts/python.exe scripts/demo_replay.py --event 2024-11-12 --speed 120       # replay the 12 Nov 2024 flood
.venv/Scripts/python.exe scripts/demo_replay.py --event 2024-11-12 --speed 0 --stop-at 09:00   # jump to 09:00
.venv/Scripts/python.exe scripts/demo_replay.py --stop                               # back to live
```

- **Admin accounts:** `python scripts/seed_admin.py --email you@example.org --role admin` (bcrypt, roles admin/viewer; viewers cannot write). Set `JWT_SECRET`. **Dev admin login** (only with `FLOODREADY_DEV_LOGIN=1` while `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `JWT_SECRET` are unset and no admin user exists; otherwise login answers 503): `admin@floodready.local` / `floodready-demo`. Set real values plus `JWT_SECRET` before deploying.
- **The API needs local data that is not in git** (§5). On a fresh clone the tests and the app build work, but the API has no archive, live logs or station lookup until §5 is done.

## 3. What is built, and where

| Area | What | Code |
| --- | --- | --- |
| Data loggers (T2–T4) | JPS Infobanjir live tables (Selangor + KL) every 15 min, MET warnings, Open-Meteo forecasts; JPS 15-min history archive | `floodready/{infobanjir,met,openmeteo,jobs,live}.py`, `scripts/run_loggers.py`, `scripts/archive_jps_history.py` |
| Stations | Lookup with names, thresholds, coordinates (data.gov.my reference list committed) | `floodready/stations.py`, `scripts/build_station_lookup.py`, `data/reference/` |
| GIS (G1–G2) | 943 BBR streets from OSM; HAND + TWI terrain susceptibility 1–5, ranked within the township | `floodready/gis/`, `assets/geo/bbr_streets.geojson` |
| Tide (G3) | Port Klang hourly tide + hours to high tide (Open-Meteo Marine) | `floodready/tide.py`, `scripts/build_tide.py` |
| Engine (E1–E6) | Features, JPS rule floor, risk matrix, street states + window, alerts (cooldown / all-clear), replay | `floodready/engine/` |
| ML (ML1–ML4) | Pooled river-crossing classifier, out-of-fold evaluation, gate, inference; fold models so replays are out-of-sample | `floodready/ml/`, `scripts/train_trigger.py`, `models/`, `config/ml.yaml` |
| API (B1, B3) | Contract endpoints, admin JWT, replay control, engine runner (live + replay) | `floodready/api/`, `scripts/serve_api.py`, `scripts/demo_replay.py` |
| Resident app (R1–R3) | Map, street page, street picker, BM/EN, live/replay ribbon, PWA with push handlers ready | `apps/resident/` |
| Contracts | API types + mocks (TS), engine types (Py), rules / matrix / ML config | `packages/shared/`, `docs/api-contract.md`, `config/` |
| Deployment (after Top 10) | systemd units for a VPS | `deploy/` |

## 4. Results to know before the pitch (honest numbers)

*Updated 17 Oct 2026 after the final retrain on the complete JPS archive (79 river stations, 233 rain gauges; 64 river stations in training). Facts for the pitch: `docs/findings.md`.*

- **12 Nov 2024 replay (BBR), per-street, real JPS data:** 08:45 rain rule: **320 streets at Watch** → 09:00: 227 at Warning → 09:30: 367 at Warning → 10:00: 298 at Danger (Sg. Binjai 4.21 m). The ML probability at Sg. Binjai (out of sample) is shown alongside: 10% at 08:30, 31% at 09:00, 51% at 09:15.
- **ML gate v2 (pre-registered): FAIL on criterion 3 → `ml_drives_alerts: false`.** ML shows a calibrated probability and the river forecast; JPS rules alone set Watch/Warning/Danger (`docs/evaluation-report.md`):
  - inland, rules alone: 795/890 crossings, 90 min median lead, 6.56 false alarms per station-month;
  - inland, rules + ML Watch: 823/890, **135 min**, 7.92 (1.21×): criteria 1–2 pass;
  - **fresh stations** (49 the EDA never saw, 467 crossings): rules 105 min, rules + ML 120 min, only +15 (needs +30): **criterion 3 fails**. Reported as is; the bar was not moved.
  - Probabilities are calibrated (Brier 0.00118, PR-AUC 0.578); tidal stations are reported separately.
- **Dead gauges:** QC found JPS river gauges frozen for months (Kg. Perepat `26558` since Jul 2024; also `26376`, `26413`, `26353`, `3017107_`, `2717134_`) and rain gauges inventing rain (26405: 2,113 mm in May 2024). 193,723 river readings are blanked; nothing at or above an alert level ever is. **85 BBR streets use `26558` as their own river** and so have no river signal: fall back to the next river station (open).
- **River forecast:** mean error vs "no change" +1 h 0.045 vs 0.061 m, +2 h 0.069 vs 0.103 m; under-forecasts flash rises (`docs/forecast-report.md`).
- **Alerts are per street** (each street's own river station and ≥ 2 rain gauges within 10 km). Watch, Warning and Danger are all pushed (`alerts.push_levels`, team decision 17 Oct 2026); expect about 17.5 messages per street in a stormy month vs 3.2 without Watch (`docs/findings.md` D1b).
- **Terrain map v2 (FABDEM + distance to drains):** 48 of 61 memorandum segments in the top two fifths (40% by chance). Pre-specified, not tuned on those streets.
- **Tide:** checked against the Port Kelang gauge: the model runs ~40 min early (corrected). 12 Nov 2024 08:00–09:00 was **low** water; say "tide was running high that week", never "flooded at high tide" (`docs/tide-check.md`).
- **Gridded rain is useless for flash floods:** 8 Open-Meteo sources showed ≤ 6.8 mm vs 79 mm at the gauge on 12 Nov 2024 (`docs/ml-feasibility.md`). That's why everything uses JPS station rain.

## 5. Data and running processes

**Not in git** (`data/raw`, `data/interim`, `logs/`). To get the API working on another machine, either copy Filbert's `data/` folder, or rebuild:

```bash
.venv/Scripts/python.exe scripts/run_loggers.py --once        # a first live snapshot
.venv/Scripts/python.exe scripts/build_station_lookup.py      # needs that live snapshot
.venv/Scripts/python.exe scripts/build_tide.py
.venv/Scripts/python.exe scripts/archive_jps_history.py       # many hours; resumable
```

**Committed:** streets GeoJSON, station reference list, models, test fixtures.

**Running on Filbert's laptop right now:** the live loggers (they also refresh the tide table once a day). The history archive is complete (310/310 series, 17 Oct 2026).

If the laptop sleeps, live logging stops (it did on 16–17 Oct). JPS gaps can be backfilled from the archive; MET warnings and forecasts can't.

**To retrain** (after new archive data or a QC change), then commit models, config and reports via a PR:

```bash
.venv/Scripts/python.exe -X utf8 scripts/qc_report.py
.venv/Scripts/python.exe -X utf8 scripts/train_trigger.py     # gate v2; rewrites config/ml.yaml + evaluation report
.venv/Scripts/python.exe -X utf8 scripts/train_forecast.py
.venv/Scripts/python.exe -X utf8 scripts/replay.py --event 2024-11-12
```

## 6. Gotchas we already paid for

| Gotcha | What we do |
| --- | --- |
| data.gov.my flood API is frozen (Feb 2024) | Use JPS Public Infobanjir (live HTML + history JSON endpoints) |
| Infobanjir rainfall page has no `<tr>` tags | Parser splits rows on the first cell |
| History rows every 5 min, only quarter hours are real | Keep quarter hours only |
| Rain: `raw = -9999` but `c15min` valid | Use `c15min`; only a missing `c15min` is missing |
| History JSON has empty values (`"cdaily":,`) | Read as null before parsing |
| Live table briefly shows `0.00` placeholders | Latest fetch of the same reading wins; `scripts/rebuild_live_tables.py` repairs from saved pages |
| History requests > ~1 month fail | Monthly chunks, cached, ≥ 3 s apart |
| Overpass refuses big queries (504) | 4×4 cached tiles with retries |
| pysheds 0.5 calls removed `np.in1d` | Shim in `floodready/gis/terrain.py` |
| Replaying with the final ML model leaks | `predict.bundle_for` picks the fold model that never saw that period |
| A slow live refresh overwrote a running replay | Generation counter in `api/runner.py` |
| Vitest 2 vs Vite 6 types | Test config lives in `apps/resident/vitest.config.ts` |
| Windows console encoding | Run Python scripts that print non-ASCII with `-X utf8` |

## 7. Next tasks (build plan IDs, by owner)

Work only on your task, on a branch, with TDD (`CLAUDE.md`). Expand your task into a step-by-step plan with superpowers:writing-plans first.

**Michael (backend)**
1. **F3 DB layer** (SQLAlchemy Core, SQLite dev / Postgres prod): alerts, subscriptions, answers, sensor readings, suggestions, notes, admin users. The runner currently keeps alerts in memory.
2. **B2 Web Push:** VAPID keys, `POST/DELETE /subscriptions`, `GET /push/public-key`, `notify(alert)` from the runner when alerts are issued (replay alerts titled `[Replay]`).
3. **B4 answers + outcomes + sensor:** `POST /answers`, outcome rules (PRD "Live benchmark"), `POST /sensor/readings`, `scripts/sim_sensor.py`.
4. **B5 admin endpoints:** stats, report, suggestions (after E7 / S1); move login to hashed passwords.
5. **B6 live tick script** for GitHub Actions (with Chingiz).

**Christian (Resident app)**
1. **R4 push:** permission flow → `POST /subscriptions`; the service worker already handles `push` and `notificationclick` (`apps/resident/src/sw.ts`); iPhone install guide.
2. **R5 verify + report:** "Is it flooding here?" sheet (Yes / No / Not sure, depth, photo, location) and "Report a flood" page.
3. **RES-6** alert history; "Mock data" ribbon when `VITE_USE_MOCKS=1` (MSW).
4. Hide the empty "rain forecast" block in replay mode.

**Darrell (UI/UX + Admin + pitch)**
1. **F4** design pass on the Resident app (tokens already in `packages/shared/src/theme/levels.ts`).
2. **A1–A4 Admin app** (`apps/admin`, copy the Resident app's setup): login, ops map with replay start/stop, street detail with station charts (`/stations/{id}/series`), statistics, report, suggestions.
3. **P1 deck** and **P2 video** storyboard. Use real screens only: replay data is real; mock screens never go in the deck.

**Chingiz (DevOps + frontend)**
1. **Branch protection on `main`:** PR + 1 approval + CI required.
2. **D1** Supabase Postgres + GitHub secrets.
3. **D2 GitHub Actions tick:** first check that Infobanjir answers GitHub runners. Then move the loggers off Filbert's laptop (Actions, or an always-on PC).
4. **D3:** Resident (and Admin) on Cloudflare Pages, API on a free host or a local + tunnel fallback. HTTPS is needed for PWA and push.
5. **A3** Admin statistics pages with Darrell.

**Filbert (engine + ML, integration)**
1. **Dead own-station fallback:** a street whose river station is dead or stale uses its next river station (85 BBR streets on `26558`).
2. **E7 backfill** 2024–2026 alerts (out-of-fold ML) → feeds Admin statistics.
3. **L1** `data/events/events.csv` (news labels with evidence quotes) → **L2** evaluation report.
4. **S1** suggestion rules SUG-1..7; **E8** Outlook (MET warnings + forecast).
5. QC follow-ups: rain gauge stuck at zero; heavy rain at one gauge while all neighbours are dry.

Done: final retrain and gate v2 (17 Oct), per-street triggers, tide check against the Port Kelang gauge.

## 8. Rules (short)

- **Git:** never commit to `main`. Branch `feat|fix|docs|ops/<area>-<short>`, conventional commits, small PRs, CI green, squash merge.
- **Contracts:** contract changes (API types, mocks, engine types, DB schema, `config/*.yaml` semantics) need the `contract` label and a backend + a frontend approval.
- **No fabricated data:** replay, demo and simulated rows are flagged and labelled on screen. ML is always evaluated out-of-sample.
- **Public repo:** no secrets, no personal data, no news article text.

## 9. Open questions for the team

1. Who records the video, and on which phone (push needs an installed PWA on iPhone)?
2. Does SDP want the 1–5 street score visible to buyers? (Ask the mentors after Top 10.)
3. Free API host choice (Chingiz): which one, given the cold-start and memory limits? The API loads ~3M archive rows into memory.
4. Should the township-wide alert behaviour ship as is for the MVP, or should per-street triggers be prioritised before the video?

- **Admin login lockout (accepted for the MVP):** 5 failed logins for one email in 15 min lock that email out (429), so an attacker can keep a known admin email locked out with bad passwords. Use another admin account or restart the API to clear it.
