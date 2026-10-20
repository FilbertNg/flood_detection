# Handoff — Flood-Ready Township

**As of 19 Oct 2026, 19:00 MYT** · Submission due **23 Oct 2026, 11:59 pm** (deck ≤ 10 slides, 5-min video, this repo)

This is the starting point for anyone (or any Claude Code session) picking up work. Read this, then [`CLAUDE.md`](CLAUDE.md) (rules) and the [build plan](docs/plans/2026-10-14-mvp-build-plan.md) (tasks and contracts). The folder map is in [README.md](README.md); every document is listed in [docs/README.md](docs/README.md).

## 1. Where we are

**The flood prediction works end to end on real data:** JPS readings → features → JPS rule floor + ML probability → street levels with time window and reasons → API → Resident app map and street page, in **live** mode (every 15 min) and **replay** mode (real past floods).

| Milestone | Status |
| --- | --- |
| M0 Foundations | Done: contracts, workspace, CI (Python + web on every PR), level theme. Design system still basic (F4) |
| M1 Engine replay | Done: `python scripts/replay.py --event 2024-11-12` |
| M2 Vertical slice | Done: Resident app shows replay and live levels from the API; Web Push backend and permission flow |
| M3 Full MVP | Code done, data not loaded: DB, push, verify/report, alert history, Admin app (map, statistics, report, suggestions, review), own-station fallback, Outlook, backfill, suggestions, all-clear hold, Watch push cap. **Still to do: load the backfill (§5), hosting + phone test (§7)** |
| M4 Ship | Not started: deck, video, submission (§7) |

Merged PRs since 15 Oct: #39 R4 push permission · #40 DB layer · #41 runbook · #42 Admin shell/map · #44 own-station fallback · #45 verify/report/history · #46 Web Push backend · #47 answers/outcomes/sensor · #48 backfill · #49 Admin statistics pages · #50 Outlook · #51 Admin API (auth, statistics, report) · #52 suggestions SUG-1..7 · #53 all-clear hold · #54 Watch push cap. Tests: **803 Python pass (1 skipped)** plus the web Vitest suites, all green in CI. The remaining-MVP plan is [docs/plans/2026-10-17-MVP2-remaining-mvp.md](docs/plans/2026-10-17-MVP2-remaining-mvp.md); day-to-day start/stop is in [docs/runbook.md](docs/runbook.md).

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
npx pnpm@9.15.0 dev:admin                                                            # admin → http://localhost:5174
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
- **Dead gauges:** QC found JPS river gauges frozen for months (Kg. Perepat `26558` since Jul 2024; also `26376`, `26413`, `26353`, `3017107_`, `2717134_`) and rain gauges inventing rain (26405: 2,113 mm in May 2024). 193,723 river readings are blanked; nothing at or above an alert level ever is. **85 BBR streets use `26558` as their own river**; while it is dead they fall back to the nearest working river station, with the reason shown first and confidence `low` (#44).
- **River forecast:** mean error vs "no change" +1 h 0.045 vs 0.061 m, +2 h 0.069 vs 0.103 m; under-forecasts flash rises (`docs/forecast-report.md`).
- **Alerts are per street** (each street's own river station and ≥ 2 rain gauges within 10 km). Watch, Warning and Danger are all pushed (`alerts.push_levels`, team decision 17 Oct 2026); expect about 17.5 messages per street in a stormy month vs 3.2 without Watch (`docs/findings.md` D1b). **Watch push cap (owner decision 19 Oct 2026):** a nowcast Watch is pushed at most once per street per 12 h (`alerts.watch_push_min_gap_h`); Warning and Danger always push, every alert is still stored and shown. It is decided in one place (`repo._capped_watch_ids`, read from the stored alerts, so it survives a restart; live and replay are capped separately; outlook rows are unaffected), so the API `push` flag and what is sent agree. BBR Apr 2024: 8,426 alerts → 7,261 pushed (p50 8, p90 12, max 30 per street; `docs/findings.md` D1e).
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

### Backfill re-run (to do before the hosting test and the video)

The Admin statistics, monthly report and suggestions read **backfill alerts** (BBR, Jan 2024 → 17 Oct 2026) from `data/floodready.db`. **None are loaded yet.** The code is final on `main` (#48 backfill with a 1-day warm-up per month, #53 all-clear hold). An earlier run (18 Oct, before #53) is superseded; a re-run was started on 19 Oct and stopped on purpose. The Watch push cap (#54) does not change stored rows, so it needs no re-run.

**Cost:** about 100 min with 5 parts in parallel (8–13 min per month per process in the 18 Oct run; about 390 MB RAM per process, seen on 19 Oct). Keep the laptop awake and on AC. Run it from a clean, up-to-date `main`. Each part writes its own SQLite file, because SQLite allows one writer at a time; each month commits on its own, so a crash loses only that month and a re-run of the same range replaces it (idempotent).

1. Start the 5 parts (PowerShell, repo root). Each line opens its own window:

   ```powershell
   git switch main; git pull
   New-Item -ItemType Directory -Force data\interim\backfill | Out-Null
   $parts = @(@('2024-01-01','2024-06-30'), @('2024-07-01','2024-12-31'), @('2025-01-01','2025-06-30'), @('2025-07-01','2025-12-31'), @('2026-01-01','2026-10-17'))
   $i = 1; foreach ($p in $parts) { Start-Process -FilePath .venv\Scripts\python.exe -ArgumentList "-X utf8 scripts\backfill.py --from $($p[0]) --to $($p[1]) --township BBR --db sqlite:///data/interim/backfill/part$i.db" -RedirectStandardOutput "data\interim\backfill\part$i.log" -RedirectStandardError "data\interim\backfill\part$i.err"; $i++ }
   ```

   Progress: `Get-Content data\interim\backfill\part*.err -Tail 2` prints one line per finished month (`backfill BBR 2024-01: N alert rows in S s`). Each part is done when its `.log` ends with `runtime … s` (a table of alert rows per month by level).
2. **Check the counts** against the earlier run. The all-clear hold removes a few percent of rows; April 2024 should be about 8,426 alert rows (8,782 before #53; `docs/findings.md` D1d), and there should be no burst of Watch rows at 00:00 on the 1st of a month.
3. **Load the parts into the app database.** Stop the API first. `db_init.py` creates the tables if `data/floodready.db` doesn't exist yet; existing live alerts, subscriptions and answers are kept:

```powershell
.venv\Scripts\python.exe scripts\db_init.py --url sqlite:///data/floodready.db
@'
import glob, sqlite3
db = sqlite3.connect("data/floodready.db")
for p in sorted(glob.glob("data/interim/backfill/part*.db")):
    db.execute("ATTACH ? AS p", (p,))
    db.execute("INSERT OR REPLACE INTO alerts SELECT * FROM p.alerts WHERE is_backfill = 1")
    db.commit()
    db.execute("DETACH p")
print("backfill alert rows:", db.execute("SELECT count(*) FROM alerts WHERE is_backfill = 1").fetchone()[0])
'@ | .venv\Scripts\python.exe -
```

4. **Suggestions** (SUG-1..7), one run per month (ids include the period, so months don't overwrite each other; admin status and notes survive re-runs). Leave out `--events` until the news labels are checked (§7):

   ```powershell
   .venv\Scripts\python.exe -X utf8 scripts\suggestions.py --from 2024-11-01 --to 2024-11-30 --township BBR --dry-run   # look first
   .venv\Scripts\python.exe -X utf8 scripts\suggestions.py --from 2024-11-01 --to 2024-11-30 --township BBR
   ```

   Expected for Nov 2024 (local dry runs in the PR #52 review, on the earlier backfill): 10 × SUG-5 (top-ranked streets by Warning/Danger episodes) and 1 × SUG-7 (`26558`, no valid data for 73% of the month). SUG-1..4 and SUG-6 stay empty until floods are confirmed by checked news labels or residents.
5. Start the API, log in to the Admin app and check Statistics (`/admin/stats`), Report (`2024-11`) and Suggestions. Then delete `data\interim\backfill\` if you want the space back.

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

## 7. What's left (as of 19 Oct 2026)

The code for the remaining-MVP plan is merged except hosting (WP14). Work on a branch with TDD (`CLAUDE.md`); merge only on an independent approval plus green CI for the head SHA. Feature freeze **21 Oct 23:59**; deck and video **22 Oct**; submit **23 Oct by 18:00**.

**Before the freeze (in this order)**

| # | Task | Who | Notes |
| --- | --- | --- | --- |
| 1 | **Backfill re-run and load** | Agent + laptop | §5 "Backfill re-run": about 100 min, then load into `data/floodready.db` and run `scripts/suggestions.py`. The Admin statistics, report and suggestions are empty until this is done. |
| 2 | **WP14 hosting** | Agent + human (accounts) | Step-by-step guide: [docs/hosting.md](docs/hosting.md). Resident and Admin on Cloudflare Pages Free; API from the laptop through Tailscale Funnel (stable `<machine>.<tailnet>.ts.net`; fallback Cloudflare Quick Tunnel, whose URL changes on restart, so Pages must be rebuilt with the new `VITE_API_URL`). Write `deploy/cloudflare/README.md` and `scripts/serve_demo.ps1`; set `CORS_ORIGINS` to the two Pages origins. |
| 3 | **Production settings** | Human | In `.env` (never in git): `JWT_SECRET` (≥ 32 bytes), VAPID keys (`scripts/gen_vapid.py`), `SENSOR_TOKEN`, optional `UPLOAD_URL_SECRET`; create real admin users with `scripts/seed_admin.py`; leave `FLOODREADY_DEV_LOGIN` unset. |
| 4 | **Rate limits behind the tunnel** | Agent | The login and answers limiters key on the client IP; behind Funnel or a tunnel every request may come from the proxy. Trust the proxy's forwarded-for header only from the tunnel, or key on device id / email (login already also keys on email). |
| 5 | **Phone end-to-end test (Android)** | Human + agent | Installed PWA over HTTPS; during a 12 Nov 2024 replay a push reaches the phone and opens the street page; "Is it flooding here?" from the phone appears in the Admin review queue; Admin statistics load from the backfill. Record as a checklist with screenshots in the WP14 PR. Each replay re-pushes `[Replay]` alerts to every real subscriber (`docs/runbook.md`). |
| 6 | **Bug bash** on both apps | Everyone | Also check: the empty "rain forecast" block in replay mode on the street page, and the "Mock data" ribbon when `VITE_USE_MOCKS=1` (both from the old R-task list; not verified as done). |

**Human tasks (only the team can do these)**

- **Check the news labels (PR #43).** Every row is still `status=draft` with `checked_by` empty and no start time, so news confirms nothing: the Nov 2024 report shows no 12 Nov event and SUG-1..4 and SUG-6 stay empty. For each row, check the quote supports the street and date, fill `checked_by`, set the status, and add `start_time_local` where the article gives it; then merge #43 and re-run `scripts/suggestions.py … --events data/events/events.csv`. After that an agent can write WP6 L2 (`scripts/evaluate_events.py`: detected? lead time vs the report; one honest failure).
- **Approve contract PR #33** (one backend and one frontend owner; never self-merge).
- **Pitch evidence (WP15):** buyer survey (30–50), 5–10 BBR resident interviews (real answers only, stored outside the public repo), cost per township for the business slide.
- **An Android phone** for the push demo and the video (iPhone push needs an installed PWA; Android is simpler).
- **Keep the laptop awake on AC** during the backfill, the hosting test, the recording and judging (`docs/runbook.md`).

**22–23 Oct**

- **Deck** (≤ 10 slides) with numbers only from `docs/findings.md` and the reports: the ML gate failure stated plainly, the dead-gauge story, the 12 Nov 2024 replay, the tidal gauge `26558` finding (D1e), the Watch push cap decision. **Don't quote the backfill confirmation rate**: news can only confirm, so it is structurally 100%.
- **Video** (≤ 5 min): the core (replay → phone push → verify → Admin statistics and suggestions → live mode) is a real screen recording on real data; the Brag skill only for the opening/closing. Label replay and the simulated sensor on screen.
- README screenshots and live links; submission checklist; submit by 18:00 on 23 Oct.

**Follow-ups (only if time is left; none blocks the MVP)**

- Contract PR: nullable, resident-only `confirmation_rate`, plus `by_level`, `alert_rows`, `street_days_with_alert` in `Kpis` (PRD ADM-4; computed already, not exposed).
- Full all-clear fix: hold until the street has been Normal *continuously* for `clear_after_min` (today the hold counts from the alert's issue time; 13% of April 2024 alerts still re-alert within 60 min of an all-clear, `docs/findings.md` D1d). Needs per-street normal-since state, an engine contract change. The Watch push cap already limits what residents receive.
- Backfill: if `ml_drives_alerts` is ever switched on, guard the 1-day warm-up at quarter starts (it uses the previous quarter's in-sample model; harmless while ML only displays a probability).
- Outlook reason text says "has an active …" even when the MET warning starts hours ahead.
- `/admin/stats` reloads and QCs the readings on every call (slow for multi-year periods): cache.
- Suggestions: SUG-7 ids carry no township (two townships sharing a station share a row); SUG-3 lacks the PRD's "similar rain" check; SUG-4's id depends on the cluster's first street.
- QC: rain gauge stuck at zero. (Heavy rain at one gauge while its neighbours are dry is usually real: 99% of rain-only Watch alerts in Apr 2024 came from a single gauge, `docs/findings.md` D1e.)
- Wording of the confirmation push for a real (non-simulated) sensor; chunked-upload size limit for photos.

Done since 15 Oct: everything in the old per-owner list except hosting (D3), the GitHub Actions tick (replaced: the API is the 15-min tick on the laptop) and Supabase (replaced: SQLite on the API host), plus own-station fallback, backfill, Outlook, suggestions, Admin API and pages, all-clear hold and Watch push cap.

## 8. Rules (short)

- **Git:** never commit to `main`. Branch `feat|fix|docs|ops/<area>-<short>`, conventional commits, small PRs, CI green, squash merge.
- **Contracts:** contract changes (API types, mocks, engine types, DB schema, `config/*.yaml` semantics) need the `contract` label and a backend + a frontend approval.
- **No fabricated data:** replay, demo and simulated rows are flagged and labelled on screen. ML is always evaluated out-of-sample.
- **Public repo:** no secrets, no personal data, no news article text.

## 9. Open questions for the team

1. Who records the video, and on which Android phone?
2. Does SDP want the 1–5 street score visible to buyers? (Ask the mentors after Top 10.)
3. Hosting stays on the laptop (Pages + Funnel) for the MVP; after Top 10, an always-on PC or VPS (`deploy/systemd`)?

- **Admin login lockout (accepted for the MVP):** 5 failed logins for one email in 15 min lock that email out (429), so an attacker can keep a known admin email locked out with bad passwords. Use another admin account or restart the API to clear it.
