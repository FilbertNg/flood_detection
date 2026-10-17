# Flood-Ready Township

Street-level flash-flood warnings for SDP townships. SDP University Hackathon 2026 · Planet → Climate resilience.

**New to the team? Read [HANDOFF.md](HANDOFF.md) first** (current status, results, next task per person), then [CLAUDE.md](CLAUDE.md) (team rules).

## Where is what

```text
sime-daby-hackathon/
│
├── README.md  HANDOFF.md  CLAUDE.md     start here: map, status, rules
├── docs/                                ALL PLANS AND DOCUMENTS → docs/README.md
│
│   ── BACKEND (Python) ─────────────────────────────────────────────
├── floodready/                          the Python package
│   ├── infobanjir.py met.py openmeteo.py tide.py   data source clients
│   ├── jobs.py live.py storage.py stations.py      loggers, archive, station lookup
│   ├── engine/                          flood engine: features → rules → risk matrix → alerts, replay
│   ├── ml/                              ML trigger: dataset, train, evaluate, predict
│   ├── gis/                             streets (OSM) + terrain susceptibility
│   └── api/                             FastAPI app (live + replay) → http://localhost:8000/docs
├── scripts/                             one runnable script per task (serve_api, run_loggers, replay, train_trigger…)
├── config/                              townships, sources, rules, risk matrix, ML thresholds (YAML)
├── models/                              trained ML models (committed)
├── tests/                               pytest; real-data fixtures in tests/fixtures/
├── pyproject.toml                       Python dependencies
│
│   ── FRONTEND (TypeScript, React + Vite) ──────────────────────────
├── apps/
│   ├── resident/                        Resident PWA (map, street page, BM/EN) → http://localhost:5173
│   └── admin/                           SDP Admin app (not started yet: tasks A1–A4)
├── packages/shared/                     API types, mocks, level colours, shared by both apps
├── package.json  pnpm-workspace.yaml    web workspace (pnpm)
│
│   ── DATA AND DEPLOYMENT ───────────────────────────────────────────
├── assets/geo/                          generated street GeoJSON (committed)
├── data/                                reference/ is committed; raw/ interim/ final/ are local only
├── notebooks/spikes/                    exploration code (not production)
├── deploy/                              VPS systemd units (after Top 10)
└── .github/workflows/ci.yml             CI: Python + web tests on every PR
```

Local only, not in git (safe to ignore in the file explorer): `.venv/`, `node_modules/`, `logs/`, `data/raw|interim|final/`, `*.egg-info/`, `.pytest_cache/`, `.playwright-mcp/`.

## How the pieces connect

```text
JPS Infobanjir, MET, Open-Meteo, OSM
        │  scripts/run_loggers.py, archive_jps_history.py, build_*.py
        ▼
data/ (raw → interim)  +  config/*.yaml  +  models/
        │  floodready/engine + floodready/ml
        ▼
floodready/api  (FastAPI, scripts/serve_api.py)
        │  HTTP, contract in docs/api-contract.md + packages/shared/src/api/types.ts
        ▼
apps/resident  (and later apps/admin)
```

## Quick start

```bash
# Backend: Python 3.12 + uv
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev,gis,ml,api]"   # .venv/bin/python on macOS/Linux
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/serve_api.py                                # API → http://localhost:8000/docs

# Frontend: Node 22
npx pnpm@9.15.0 install
npx pnpm@9.15.0 dev:resident                                                 # app → http://localhost:5173
npx pnpm@9.15.0 test

# Demo: replay the real 12 Nov 2024 flood (needs the API running)
.venv/Scripts/python.exe scripts/demo_replay.py --event 2024-11-12 --speed 120
.venv/Scripts/python.exe scripts/demo_replay.py --stop                       # back to live
```

The API needs local data that is not in git. On a fresh clone see [HANDOFF.md §5](HANDOFF.md#5-data-and-running-processes). Logger, archive and deployment details are in [HANDOFF.md](HANDOFF.md) and [deploy/README.md](deploy/README.md).

Data credits: © OpenStreetMap contributors · JPS Public Infobanjir · MET Malaysia (via data.gov.my) · Open-Meteo (CC BY 4.0) · Terrain: Copernicus GLO-30, FABDEM (© University of Bristol, CC BY-NC-SA 4.0, non-commercial), ESA WorldCover 2021 (CC BY 4.0).

## License

The code is licensed under the [Apache License 2.0](LICENSE). Data and data-derived files keep their own licences and are not covered by it: street geometry in `assets/geo/` is from OpenStreetMap (ODbL), and its susceptibility columns derive from FABDEM (CC BY-NC-SA 4.0, non-commercial, share-alike); see [assets/geo/NOTICE.md](assets/geo/NOTICE.md). JPS, MET Malaysia and Open-Meteo data are used under their providers' terms and are not redistributed in this repository.
