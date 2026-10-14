# Flood-Ready Township

SDP University Hackathon 2026 · Planet → Climate resilience.

Plan documents (current versions):

- [Flood-Ready Township — PRD.md](Flood-Ready%20Township%20—%20PRD.md): product, requirements, demo
- [Flood-Ready Township — Training Data Spec.md](Flood-Ready%20Township%20—%20Training%20Data%20Spec.md): data sources, tables, task list (T1–T17)
- [Flood-Ready Township — Plan Review.md](Flood-Ready%20Township%20—%20Plan%20Review.md): why v1 changed (`archive/` holds v1)

## Setup

```bash
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"   # Windows path; use .venv/bin/python elsewhere
.venv/Scripts/python.exe -m pytest -q
```

## Data loggers (T2, T3): keep these running

```bash
.venv/Scripts/python.exe scripts/run_loggers.py          # loop: JPS + MET every 15 min, forecast hourly
.venv/Scripts/python.exe scripts/run_loggers.py --once   # one pass (for Task Scheduler / cron)
```

Live data can't be recovered later, so run the loop on a machine that never sleeps (a desktop, Raspberry Pi or free-tier VM). On Windows you can also schedule `--once` every 15 minutes with Task Scheduler.

Health check: `data/raw/jps_live/_status.json` (`"ok": true`, few stale stations), plus `logs/loggers.log`.

## JPS history archive (T4)

```bash
.venv/Scripts/python.exe scripts/archive_jps_history.py
```

Downloads 15-min station history (rain from Jan 2024, water level from Apr 2024) for township stations, then every station in the districts in `config/sources.yaml`. It takes many hours at a polite pace and is resumable: every monthly chunk is cached, so just run it again after a stop or to retry failed chunks. Progress: `data/raw/jps_hist/_progress.json`, `logs/archive.log`.

## See the flood prediction working (local)

```bash
.venv/Scripts/python.exe scripts/serve_api.py                 # API on http://localhost:8000 (docs at /docs)
npx pnpm@9.15.0 install && npx pnpm@9.15.0 dev:resident     # Resident app on http://localhost:5173
.venv/Scripts/python.exe scripts/demo_replay.py --event 2024-11-12 --speed 120     # replay the 12 Nov 2024 flood
.venv/Scripts/python.exe scripts/demo_replay.py --stop                              # back to live
```

- **Live mode** (default) recomputes every 15 minutes from the logged JPS data.
- **Replay** walks a real past flood from the JPS archive, with ML probabilities from a model that never trained on that period.
- `--speed 0 --stop-at 09:00` jumps straight to a moment.
- Engine-only timeline: `python scripts/replay.py --event 2024-11-12`.

## Deployment

On a VPS the loggers run as a systemd service that restarts automatically, and a nightly timer tops up the history archive. See [deploy/README.md](deploy/README.md).

## Layout

```text
config/       townships.yaml (centres, named JPS stations), sources.yaml (endpoints, polling, archive)
floodready/   Python package: infobanjir parsers, MET and Open-Meteo clients, storage, jobs
scripts/      runnable tasks (one per spec task)
deploy/       systemd units and deployment notes
tests/        pytest, using real responses saved in tests/fixtures
data/         raw/ interim/ final/ (not in git)
```

Data credits: JPS Public Infobanjir, MET Malaysia via data.gov.my, Open-Meteo (CC BY 4.0), © OpenStreetMap contributors.
