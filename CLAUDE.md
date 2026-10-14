# Flood-Ready Township: guide for Claude Code

Street-level flash-flood warnings for SDP townships (SDP University Hackathon 2026). **Full MVP due 23 Oct 2026, 11:59 pm**: deck (≤ 10 slides), 5-min video, this repo.

## Read first

- `HANDOFF.md`: **current state, how to run, results, gotchas, next tasks per person** (start here).
- `docs/superpowers/plans/2026-10-14-mvp-build-plan.md`: **the build plan**. Tasks, owners, contracts (§4), git rules (§9). Work only on your assigned task; expand it into a TDD plan with superpowers:writing-plans before coding.
- `Flood-Ready Township — PRD.md`: product requirements.
- `Flood-Ready Township — Training Data Spec.md`: data sources and schemas.
- `docs/api-contract.md`: API contract (once F1 is merged).

## Commands

```bash
# Python (3.12)
uv venv .venv && uv pip install --python .venv/Scripts/python.exe -e ".[dev]"   # .venv/bin/python on macOS/Linux
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/run_loggers.py --once
# Web (after F2): pnpm i && pnpm -C apps/resident dev / pnpm -C apps/admin dev / pnpm -r test
```

## Rules

- **TDD:** write the failing test first, watch it fail, then implement. Tests use real data fixtures in `tests/fixtures/` where possible.
- **Never fabricate data.** No invented readings, events, answers or statistics. Simulated, replay and demo rows are flagged (`simulated`, `is_replay`, `source='demo'`), labelled on screen, and excluded from statistics.
- **ML is evaluated honestly:** time-blocked folds, never score a period with a model trained on it (backfill uses out-of-fold probabilities), features use only data at or before t, and always compare against the JPS rule baseline. The ML trigger may raise a level, never lower an official threshold.
- **Contracts are frozen** (build plan §4: levels, IDs, API shapes, DB tables, engine interfaces). Changing one needs a PR labelled `contract`, approved by one backend and one frontend owner, with mocks updated.
- **Times** are MYT (UTC+8). API timestamps are ISO 8601 with `+08:00`.
- **Git:** never commit to `main`. Branch `feat|fix|docs|ops/<area>-<short>`, conventional commits, small PRs, one approval + green CI, squash merge. Never force-push shared branches. End commit messages with the Co-Authored-By line your Claude Code session gives you.
- **Public repo:** no secrets (`.env` is ignored; use GitHub Actions secrets), no personal data, no raw news article text (facts, evidence quote and URL only).
- **Data credits** on every map: © OpenStreetMap contributors · JPS Public Infobanjir · MET Malaysia · Open-Meteo.
- **JPS Infobanjir is scraped politely:** live tables every 15 min, history ≥ 3 s between requests, everything cached.

## Layout

```text
floodready/   Python: infobanjir/met/openmeteo clients, jobs, engine/, gis/, db/, api/, stats/, push.py
scripts/      one runnable script per task
config/       townships.yaml, sources.yaml, rules.yaml, risk_matrix.yaml
apps/         resident (PWA), admin            (React + Vite + TS + react-leaflet)
packages/     shared (api types/client, map components, theme, i18n, mocks)
assets/geo/   generated street GeoJSON (committed)
data/         raw/ interim/ final/ are NOT in git; data/events/events.csv is
deploy/       VPS systemd units (after Top 10)
```
