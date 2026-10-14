# Handoff — Flood-Ready Township

**As of 15 Oct 2026, 02:00 MYT** · Submission due **23 Oct 2026, 11:59 pm** (deck ≤ 10 slides, 5-min video, this repo)

This is the starting point for anyone (or any Claude Code session) picking up work. Read this, then [`CLAUDE.md`](CLAUDE.md) (rules) and the [build plan](docs/superpowers/plans/2026-10-14-mvp-build-plan.md) (tasks and contracts).

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

- **Dev admin login** (only while `ADMIN_EMAIL` / `ADMIN_PASSWORD` are unset): `admin@floodready.local` / `floodready-demo`. Set real values plus `JWT_SECRET` before deploying.
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

- **12 Nov 2024 replay (BBR), real JPS data:** Watch 08:45 (45 mm/1 h at Kg. Perepat) → Warning 09:00 (61.5 mm) → Danger 10:00 (Sg. Binjai 4.21 m). Persiaran Sungai Keramat, which really flooded that morning, shows Warning, window 09:30–10:30, ML 54% (out-of-sample).
- **ML gate: FAIL → `ml_drives_alerts: false`.** ML is shown as an informational probability; JPS rules decide alert levels. Out-of-fold over the stations archived so far (`docs/evaluation-report.md`):
  - rule floor: 862/870 crossings, 45 min median lead, 6.74 false alarms per station-month;
  - ML (p ≥ 0.25): 819/870, 150 min, 6.66.
  - The tidal Bandar Klang station holds ~67% of crossings. Without it, ML gives ~30 min more lead with slightly fewer false alarms but misses more. At BBR's own river (Pekan Meru) the floor is clearly better.
- **Terrain map (no flood labels used):** 62% of memorandum street segments rank in the top two fifths, vs 40% by chance. A real but modest signal.
- **Tide vs news:** the tide model puts the 12 Nov 2024 morning at **low** tide (high ≈ 02:00 and ≈ 14:00), while the news said "high tide". Don't say "high tide" in the pitch until it's checked against JUPEM tables.
- **Gridded rain is useless for flash floods:** 8 Open-Meteo sources showed ≤ 6.8 mm vs 79 mm at the gauge on 12 Nov 2024 (`docs/ml-feasibility.md`). That's why everything uses JPS station rain.
- **Alerts are township-wide:** at Warning, ~40% of BBR streets alert together. Per-street triggers (nearest stations) are a later refinement.

## 5. Data and running processes

**Not in git** (`data/raw`, `data/interim`, `logs/`). To get the API working on another machine, either copy Filbert's `data/` folder, or rebuild:

```bash
.venv/Scripts/python.exe scripts/run_loggers.py --once        # a first live snapshot
.venv/Scripts/python.exe scripts/build_station_lookup.py      # needs that live snapshot
.venv/Scripts/python.exe scripts/build_tide.py
.venv/Scripts/python.exe scripts/archive_jps_history.py       # many hours; resumable
```

**Committed:** streets GeoJSON, station reference list, models, test fixtures.

**Running on Filbert's laptop right now:**
- live loggers (since 14 Oct; restarted on 15 Oct after the placeholder fix);
- the history archive (**82/310** stations; Klang done, Petaling/KL in progress; hours left);
- the API on :8000 and the Resident dev server on :5173.

If the laptop sleeps, live logging stops. JPS gaps can be backfilled from the archive; MET warnings and forecasts can't.

**When the archive finishes:**

```bash
.venv/Scripts/python.exe scripts/build_station_lookup.py
.venv/Scripts/python.exe -X utf8 scripts/train_trigger.py     # retrains on all stations, rewrites config/ml.yaml + report
```

Then restart the API, and commit the new models, config and report via a PR.

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
1. Retrain ML when the archive completes (§5). Re-check the gate with tide plus all stations.
2. **E7 backfill** 2024–2026 alerts (out-of-fold ML) → feeds Admin statistics.
3. **L1** `data/events/events.csv` (news labels with evidence quotes) → **L2** evaluation report.
4. **S1** suggestion rules SUG-1..7; **E8** Outlook (MET warnings + forecast).
5. Per-street triggers (nearest stations) to reduce township-wide alerts.
6. Check JUPEM tide tables for 12 Nov 2024.

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
