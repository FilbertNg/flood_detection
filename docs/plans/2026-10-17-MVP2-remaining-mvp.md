# Remaining MVP (M2 → M4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. This is a roadmap: each work package (WP) below is expanded into its own step-by-step TDD plan (`docs/plans/2026-10-1x-<WP id>-<name>.md`) when it is dispatched, using the Files, Interfaces and Acceptance tests given here. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish everything the 23 Oct 2026 submission needs on top of the merged engine: database, push, resident verification, backfill, statistics and suggestions, the Admin app, hosting, the video and the deck.

**Architecture:** One FastAPI process (`floodready/api`) keeps running the engine (live every 15 min, replay on demand) and now also persists street states, alerts, subscriptions and answers through a SQLAlchemy Core repository (`floodready/db`). Push goes out from the same process when an alert with `push: true` is issued. A one-off backfill writes 2024–2026 alerts into the same tables; statistics, reports and suggestions are pure functions over those tables. Two React apps (Resident PWA, new Admin app) read the API.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 Core (SQLite for dev and the demo host, Postgres-compatible types), pywebpush (VAPID), PyJWT + bcrypt, Pillow (EXIF strip); React 19 + Vite 6 + react-router 7 + react-leaflet 5, vitest; Cloudflare Pages + Cloudflare Tunnel.

## Global Constraints

- Deadline: **23 Oct 2026, 11:59 pm MYT**; submit by **23 Oct 18:00** (build plan §11: ≥ 6 h early). Feature freeze **21 Oct 23:59**.
- Contracts are frozen (build plan §4): API shapes in `docs/api-contract.md` + `packages/shared/src/api/types.ts`, DB tables in build plan §4.3. All types needed below (`AlertSummary`, `AnswerForm`, `Stats`, `Report`, `Suggestion`, `Answer`, `SubscriptionRequest`, `PushPayload`, …) already exist; implement to them. Any shape change → PR labelled `contract`, approved by one backend and one frontend owner.
- **Never fabricate data.** Backfill outcomes come only from news labels with an evidence quote and URL, or real resident answers. Simulated / replay / demo rows are flagged (`is_replay`, `is_backfill`, `simulated`, `source='demo'`), labelled on screen and excluded from statistics.
- ML: `config/ml.yaml` `ml_drives_alerts: false` (gate v2 failed criterion 3, 17 Oct). ML probability is shown, never sets a level. Backfill uses out-of-fold fold models (`predict.bundle_for(..., live=False)`).
- Alerts: `alert_levels [watch, warning, danger]`; **push** `push_levels [watch, warning, danger]` (team decision 17 Oct); all-clears never pushed; nowcast window only from **Warning** (`window_from: warning`, decision 17 Oct).
- Radar stays off (`radar.enabled: false`) until MET Malaysia gives written consent.
- Privacy: no accounts; random `device_id`; location rounded to 3 decimals; photo EXIF stripped; no names/phones/addresses.
- Times MYT; API timestamps ISO 8601 `+08:00`. Credits on every map; footer "Advisory only. JPS, MET and NADMA are the official sources." on alert and street pages.
- TDD (pytest / vitest); conventional commits ending with the session's Co-Authored-By line; never commit to `main`; merge only after an independent reviewer's APPROVE and green CI **for the PR's head SHA**.
- Agents work in isolated worktrees and **never create junctions/symlinks** to `data/`; they read real data by absolute path, read-only.
- Archive readings (25 M rows) stay in parquet (`data/raw/jps_hist`); the DB holds states, alerts, answers, subscriptions, suggestions, notes, sensor rows and admin users — not the archive.

---

## 1. Where we are (17 Oct 2026)

| Area | Done | Missing |
| --- | --- | --- |
| Engine + ML + QC | Live and replay, per-street, dead-gauge QC, final retrain, river forecast, tide | Own-station fallback for streets on a dead gauge (85 BBR streets on `26558`); Outlook (E8) |
| API | `GET status/streets/streets/{id}/stations/series/alerts`, `POST admin/login`, `POST/DELETE admin/replay` | DB persistence (alerts are in memory), push, answers, sensor, admin stats/report/suggestions/answers/notes |
| Resident app | Home map, street page, pick streets, Watch banner, credits, BM/EN | Push permission (R4), verify + report (R5), alert history (RES-6), install guide |
| Admin app | — (no `apps/admin`) | All of A1–A4 (+ ADM-7 review queue) |
| Database | — (no `floodready/db`) | All of F3 |
| Labels | — (`data/events/events.csv` does not exist) | L1 news labels, L2 event evaluation |
| Hosting | Laptop only | D3 (Pages + tunnel), D2 decision |
| Pitch | `docs/findings.md` | Survey/interviews, deck (P1), video (P2) |

## 2. Decisions this plan makes (change them before dispatch if you disagree)

*All five approved by the product owner on 17 Oct 2026.*

1. **SQLite on the API host for the MVP demo**, through SQLAlchemy Core with portable types and a `DATABASE_URL`. Postgres (Supabase) works by URL but is a stretch goal. Reason: the API must run where the parquet archive and live logs are (the laptop or an always-on PC); a remote DB adds a failure point and no demo value.
2. **The API process is the tick.** The existing runner already refreshes live data every 15 min; it now also persists and pushes. A separate GitHub Actions tick (D2) is dropped for the MVP (JPS may block foreign runners; the laptop logger already runs).
3. **Hosting:** both apps on **Cloudflare Pages (Free)**, checked 17 Oct against Cloudflare's docs: 500 builds/month, 1 concurrent build, 20 min build timeout, 20,000 files and 25 MiB per file per site, HTTPS included, and with no top-level `404.html` Pages "assumes that you are deploying a single-page application" and serves `/` for unknown paths, so react-router deep links (`/street/<id>`) work. The API runs on the laptop/PC and is exposed over HTTPS by:
   - **Tailscale Funnel (recommended):** free on all plans, HTTPS certificates automatic, ports 443/8443/10000 only, bandwidth limited (not published), hostname is the machine's `<machine>.<tailnet>.ts.net` name, so the Pages build's `VITE_API_URL` stays valid across restarts (confirm on first setup).
   - **Fallback, Cloudflare Quick Tunnel:** free, no account, but "the hostname changes each time", up to 200 in-flight requests, no Server-Sent Events (we use none), "for testing and development" with no uptime guarantee. After each restart, redeploy the Pages build with the new `VITE_API_URL` (`wrangler pages deploy`, about a minute).
   - A named Cloudflare Tunnel gives a stable URL only with a domain on Cloudflare (paid domain); not needed.
4. **Backfill scope: BBR only** (build plan §10 scope guard item 3).
5. **Push is demonstrated on Android Chrome** (iPhone needs an installed PWA, iOS 16.4+; the install guide still ships).

## 3. Interfaces (exact names; every WP codes to these)

### 3.1 Repository (`floodready/db/repo.py`, WP1)

```python
def connect(url: str) -> sqlalchemy.Engine                       # creates tables if missing (metadata.create_all)
def save_street_states(conn, states: list[StreetState], mode: str) -> None          # upsert on (street_id, mode)
def get_street_states(conn, township_id: str, mode: str) -> list[dict]
def insert_alerts(conn, alerts: list[Alert], *, is_replay: bool, is_backfill: bool) -> list[str]   # returns alert_ids
def list_alerts(conn, *, street_id: str | None = None, active: bool = False,
                include_replay: bool = True, since: datetime | None = None) -> list[dict]          # AlertSummary dicts
def upsert_subscription(conn, device_id: str, sub: dict, street_ids: list[str], lang: str) -> None
def delete_device(conn, device_id: str) -> None                  # deletes subscriptions, subscription_streets and the device's answers (+ photos): "deletes all data for the device" (§4.2)
def list_subscribers(conn, street_id: str) -> list[dict]         # {device_id, endpoint, p256dh, auth, lang}
def insert_answer(conn, answer: dict) -> str                     # raises DuplicateAnswer on (device_id, alert_id)
def list_answers(conn, *, alert_id=None, street_id=None, review_status=None) -> list[dict]
def set_answer_review(conn, answer_id: str, status: str) -> None
def insert_sensor_reading(conn, device_id: str, time_local: datetime, level_cm: float, simulated: bool) -> None
def upsert_suggestions(conn, suggestions: list[dict]) -> None
def update_suggestion(conn, suggestion_id: str, status: str, note: str | None) -> None
def insert_note(conn, street_id: str, text: str, author: str) -> int
class DuplicateAnswer(Exception): ...
```

### 3.2 Push (`floodready/push.py`, WP3)

```python
def payload(alert: dict, street_name: str, lang: str) -> dict    # PushPayload: {title, body, url: "/street/<id>", alert_id, level}; "[Replay] " title prefix when is_replay
def notify(conn, alert: dict, street_name: str, send=webpush) -> int   # sends to subscribers of alert.street_id when alert["push"]; deletes subs on 404/410; returns sent count
```

### 3.3 Outcomes, stats, suggestions (`floodready/stats/`, WP4, WP6, WP7)

```python
# outcomes.py
def alert_outcome(answers: list[dict], sensor_above: bool) -> str            # confirmed | not_confirmed | unverified (PRD "Live benchmark")
def missed_floods(reports: list[dict], alerts: list[dict]) -> list[dict]     # report backed by 2 devices (1 with photo), no warning/danger in previous 3 h
def news_outcomes(events: pd.DataFrame, alerts: list[dict]) -> dict[str, str] # alert_id -> "confirmed" when a labelled event matches street/time
# statistics.py
def stats(conn, date_from: date, date_to: date) -> dict                      # Stats shape; excludes is_replay and source='demo'
# report.py
def monthly_report(conn, month: str) -> dict                                 # Report shape
# suggestions.py
def suggestions(conn, date_from: date, date_to: date, tide: pd.DataFrame, station_health: list[dict]) -> list[dict]  # SUG-1..7
```

### 3.4 Engine additions

```python
# floodready/engine/street_stations.py (WP2)
def wl_for(mapping, street_id, dead_or_stale: set[str] | None = None) -> str | None   # own river station, else next one in the street's candidate list
# floodready/engine/backfill.py (WP5)
def run_backfill(start: datetime, end: datetime, township_id: str, conn, step=timedelta(minutes=15)) -> dict[str, int]  # alerts per month
# floodready/engine/outlook.py (WP9)
def township_outlook(met_warnings: list[dict], forecast: pd.DataFrame, now: datetime, cfg: dict) -> Alert | None
```

## 4. Work packages

Each WP lists files, the acceptance tests its TDD plan must contain (written first, seen failing), and who/what model does it. "Agent" = implementer (Sonnet) + independent reviewer (Opus for data/ML/safety/security, Sonnet otherwise). "Human" = a teammate must do it.

### WP1 — Database layer (F3) · Agent · critical path

**Files:** Create `floodready/db/__init__.py`, `floodready/db/schema.py` (all build-plan §4.3 tables), `floodready/db/repo.py` (§3.1), `scripts/db_init.py`, `tests/db/test_repo.py`. Modify `pyproject.toml` (`sqlalchemy>=2` in `api` extras; `psycopg[binary]` in a new `postgres` extra).

**Acceptance tests (SQLite in-memory):**
- `test_states_round_trip`: `save_street_states` then `get_street_states` returns every field (level, trigger_level, confidence, flood_probability, fired_by, window, reasons, data_time) unchanged; saving again replaces, not duplicates.
- `test_alert_ids_and_flags`: `insert_alerts(..., is_replay=True)` returns unique ids; `list_alerts(include_replay=False)` excludes them; `active=True` returns only the latest non-all-clear per street within its window or cooldown.
- `test_duplicate_answer`: second `insert_answer` for the same `(device_id, alert_id)` raises `DuplicateAnswer`; two `report` answers with `alert_id=None` from one device are both stored.
- `test_delete_device`: removes the subscription, its street links, the device's answers and their photo files; other devices' rows are untouched.
- `test_postgres_types`: `schema.metadata` compiles for the `postgresql` dialect without errors.
- `scripts/db_init.py --url sqlite:///data/floodready.db` creates every table (asserted by inspecting the file).

### WP2 — Street own-station fallback · Agent (Opus review: safety)

**Files:** Modify `floodready/engine/street_stations.py`, `floodready/engine/replay.py` (pass dead/stale set), `floodready/api/serialize.py` (`river_forecast_for` uses the same choice), `scripts/build_street_stations.py` (store an ordered candidate list `wl_candidates` per street). Test: `tests/engine/test_street_stations.py`, `tests/engine/test_per_street.py`.

**Acceptance tests:**
- A street mapped to `26558` with `26558` in the dead set uses its next candidate (`PEKANMERU` in the real mapping) for river rules, ML probability and river forecast; the reason text names the fallback station.
- When no candidate is alive, the street keeps rain rules only and gets a `stale_data` reason (level never lowered silently).
- 12 Nov 2024 replay: the 85 streets formerly on `26558` now show a non-null `flood_probability` at 09:00; street counts per level printed before/after in the PR body.
- The dead set comes from QC flags at time t (no look-ahead): a test where the station becomes dead after t keeps it at t.

### WP3 — Web Push backend (B2) · Agent (Opus review: security)

**Depends:** WP1. **Files:** Create `floodready/push.py`, `scripts/gen_vapid.py`, `tests/test_push.py`, `tests/api/test_subscriptions.py`. Modify `floodready/api/main.py` (`GET /push/public-key`, `POST /subscriptions`, `DELETE /subscriptions/{device_id}`), `floodready/api/runner.py` (persist states/alerts via repo; call `push.notify` for new alerts with `push: true`), `pyproject.toml` (`pywebpush`), `.env.example` (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`, `DATABASE_URL`).

**Acceptance tests:**
- Subscribing stores device + streets; `notify` sends only to subscribers of that street, in their language (EN/MS strings from the existing reason text), payload exactly `PushPayload`.
- A 404/410 from the push service deletes that subscription; other errors are logged and do not stop the tick.
- Replay alerts are pushed with title prefix `[Replay]`; all-clears are not pushed.
- Restarting the API keeps alerts (read back from the DB) and does not re-push them (idempotent on `alert_id`).
- No VAPID key in the repo; missing keys → push disabled with one warning, API still serves.

### WP4 — Answers, reports, sensor, outcomes (B4) · Agent

**Depends:** WP1. **Files:** Create `floodready/stats/__init__.py`, `floodready/stats/outcomes.py`, `scripts/sim_sensor.py`, `tests/stats/test_outcomes.py`, `tests/api/test_answers.py`. Modify `floodready/api/main.py` (`POST /answers` multipart, `POST /sensor/readings` with `SENSOR_TOKEN`), `pyproject.toml` (`Pillow`, `python-multipart`).

**Acceptance tests:**
- Outcome rules verbatim from PRD "Live benchmark": 2 distinct yes within 3 h → confirmed; 1 yes with photo → confirmed; 3 no and 0 yes → not_confirmed; no answers → unverified; sensor above threshold → confirmed; answers > 1 km away count half.
- A `report` with no Warning/Danger on that street in the previous 3 h, backed by 2 devices (or 1 with photo) → missed flood.
- `POST /answers` twice for the same alert → 409; photo is saved without EXIF (test reads it back with Pillow and finds no EXIF); lat/lon stored rounded to 3 decimals.
- When an alert turns confirmed, its street's subscribers get exactly one "Confirmed by neighbours" push.
- `sim_sensor.py --curve rise` posts readings with `simulated=true`; statistics exclude them.

### WP5 — Backfill 2024–2026, BBR (E7) · Agent (Opus review: honest ML)

**Depends:** WP1, WP2. **Files:** Create `floodready/engine/backfill.py`, `scripts/backfill.py`, `tests/engine/test_backfill.py`.

**Acceptance tests:**
- Over 12 Nov 2024 06:00–14:00 the backfill produces the same alerts as `replay.run`, flagged `is_backfill=1`.
- ML probabilities come from the fold model that never trained on that quarter (`bundle_for(..., live=False)`), asserted per row against `dataset.fold_of`.
- Re-running a month replaces that month's backfill rows (idempotent).
- Full run 2024-01-01 → 2026-10-17 for BBR completes; the PR body prints alerts per month by level and the runtime. Run in the background; one month first to estimate time.

### WP6 — News labels (L1) + event evaluation (L2) · Agent drafts, **Human checks every row**

**Files:** Create `data/events/events.csv` (schema: training-data-spec Dataset 1), `tests/test_events_schema.py`, `scripts/evaluate_events.py`; append a section to `docs/evaluation-report.md`.

**Acceptance tests / rules:**
- Schema test: required columns, enums, non-empty `evidence_quote` (≤ 300 chars, no full article text) and `source_url`, `checked_by` filled by a human.
- Contains the 6 seed incidents plus every Klang / Petaling / KL flash flood found for 2024-01 → today that names a BBR street or area; each row's quote supports its street/date claim.
- `evaluate_events.py`: for each labelled BBR event, detected? first Watch/Warning time vs report time; Warning days per month over the backfill. Report one honest failure.
- `news_outcomes` (WP4 interface) marks matching backfill alerts `confirmed` with `source='news'`.

### WP7 — Suggestions SUG-1..7 (S1) · Agent

**Depends:** WP4, WP5, WP6. **Files:** Create `floodready/stats/suggestions.py`, `tests/stats/test_suggestions.py`.

**Acceptance tests:** one synthetic case per rule triggers exactly that rule with its evidence and PRD priority (SUG-1: 3 confirmed floods with onset rain 35, 42, 48 mm → "drainage capacity review"; SUG-2: ≥ 70% of ≥ 2 floods within ±2 h of high tide; SUG-3: neighbour comparison / year-on-year ≥ 2×; SUG-4: ≥ 3 adjacent S4–5 streets with repeated floods; SUG-5: ≥ 5 Warning/Danger; SUG-6: ≥ 2 missed floods; SUG-7: station stale > 10% of the period — **the dead gauges `26558`, `26376`, `26413`, `26353`, `3017107_`, `2717134_` count as stale while dead**). Every text ends "Screening suggestion; site survey needed."

### WP8 — Admin endpoints (B5) · Agent (Opus review: auth)

**Depends:** WP1, WP4, WP7. **Files:** Create `floodready/api/auth.py` (bcrypt hashes, JWT), `floodready/stats/statistics.py`, `floodready/stats/report.py`, `scripts/seed_admin.py`, `tests/api/test_admin.py`. Modify `floodready/api/main.py` (`GET /admin/stats`, `GET /admin/report`, `GET/PATCH /admin/suggestions`, `GET/PATCH /admin/answers`, `POST /admin/notes`), move login from the dev constant to `admin_users`.

**Acceptance tests:** wrong password → 401; every `/admin/*` without a token → 401; viewer role cannot PATCH; `GET /admin/stats` over the backfill matches the `Stats` type with replay/demo rows excluded (a seeded replay alert does not change the counts); `GET /admin/report?month=2024-11` lists the 12 Nov 2024 event; station health lists `26558` as stale/dead.

### WP9 — Outlook 6–24 h (E8) · Agent

**Depends:** WP1. **Files:** Create `floodready/engine/outlook.py`, `floodready/met_parse.py`, `tests/engine/test_outlook.py`; modify the runner to issue outlook alerts (horizon `outlook`, confidence `medium`).

**Acceptance tests:** build-plan E8 verbatim (MET fixture naming Selangor → active; 45 mm over 18:00–21:00 → window 18:00–21:00; 5 mm and no warning → none; 60 min cooldown); reason text says forecasts often miss tropical storms.

### WP10 — Resident: push permission + install guide (R4) · Agent

**Depends:** WP3 (or a stubbed fetch in tests). **Files:** Create `apps/resident/src/push/subscribe.ts`, `apps/resident/src/components/InstallGuide.tsx`; modify `apps/resident/src/sw.ts` (notificationclick → `/street/<id>`), `apps/resident/src/routes/PickStreets.tsx` (ask permission after saving streets), `apps/resident/src/lib/i18n.ts`.

**Acceptance tests (vitest):** granting permission posts `SubscriptionRequest` with the saved streets and language; denied → explanation shown, no POST; changing streets re-posts; notification click opens `/street/<id>`; iPhone Safari not installed → install guide shown.

### WP11 — Resident: verify, report, alert history (R5, RES-6) · Agent

**Depends:** WP4 (or stubbed fetch). **Files:** Create `apps/resident/src/components/VerifySheet.tsx`, `apps/resident/src/routes/Report.tsx`, `apps/resident/src/components/AlertHistory.tsx`; modify `Street.tsx`, `App.tsx`, `i18n.ts`.

**Acceptance tests:** Yes/No/Not sure + depth + optional photo + optional location posted as multipart `AnswerForm`; 409 → "You already answered"; report works with no active alert; alert history lists each alert with its outcome badge (confirmed / not confirmed / unverified) and a Replay tag for replay alerts.

### WP12 — Admin app shell, login, ops map, street detail (A1, A2) · Agent

**Files:** Create `apps/admin/` (copy `apps/resident` tooling: `package.json`, `vite.config.ts`, `vitest.config.ts`, `tsconfig.json`), `src/main.tsx`, `src/App.tsx`, `src/auth.ts`, `src/routes/{Login,OpsMap,StreetDetail}.tsx`, `src/components/StationChart.tsx`; root `package.json` script `dev:admin`; CI web job runs its tests.

**Acceptance tests:** token in memory + sessionStorage; any 401 → login; nav Map / Statistics / Reports / Suggestions / Review; ops map colours streets by level and greys stale stations; street detail draws rain and river series with threshold lines from `/stations/{id}/series`; replay start/stop buttons call `/admin/replay`; credits on the map.

### WP13 — Admin statistics, report, suggestions, review (A3, A4, ADM-7) · Agent

**Depends:** WP8, WP12. **Files:** Create `apps/admin/src/routes/{Statistics,Report,Suggestions,Review}.tsx`, `src/components/{KpiTiles,ByWeekChart,ByStreetTable,RainAtOnsetChart}.tsx`, print stylesheet.

**Acceptance tests:** period filter refetches `/admin/stats`; KPI tiles show counts and "unverified is never a false alarm"; data-source note shows news vs resident counts; report month picker, print preview fits A4; suggestions ranked by priority with evidence and status buttons (PATCH); review queue marks answers valid/spam.

### WP14 — Hosting and end-to-end (D3) · Agent + Human (phone, accounts)

**Depends:** WP3, WP10, WP12. **Files:** Create `deploy/cloudflare/README.md` (Pages projects for `apps/resident` and `apps/admin`, build command, `VITE_API_URL`, Tailscale Funnel and Quick Tunnel commands), `scripts/serve_demo.ps1` (API + funnel/tunnel), API `CORS_ORIGINS` set to the two Pages origins, README "Live links" and setup update.

**Acceptance:** both apps load on a phone over HTTPS; the Resident PWA installs on Android; during a 12 Nov replay a push reaches the phone and opens the street page; "Is it flooding here?" from the phone appears in the Admin review queue; the admin stats page loads from the backfill. Recorded as a checklist with screenshots in the PR.

### WP15 — Pitch evidence (Human) · starts now, in parallel

- **Buyer survey (30–50) and 5–10 BBR resident interviews** (PRD "Team, Evidence & Pitch Quality"). Real responses only; store answers outside the public repo; summarise counts in the deck.
- **Approve contract PR #33** (one backend + one frontend owner).
- **Check every news-label row** from WP6 (`checked_by`).
- **Cost per township** for the commercial slide (hosting, SMS-free push, staff time).

### WP16 — Deck and video (P1, P2) · Human lead, agent support

**Depends:** feature freeze. Deck ≤ 10 slides per build plan P1, with numbers only from `docs/findings.md` and the reports (gate failure stated plainly; dead-gauge story; 12 Nov replay). Video ≤ 5 min per build plan P2 script, recorded on the WP14 setup at 1080p with captions; replay and simulated sensor labelled on screen.

**Video tooling (product owner, 17 Oct):** the team plans to use the **Brag** skill (`/brag`, Hyperframes; reads the project code and makes a short launch video). Use it for the video's opening/closing or a teaser. The P2 core (replay → phone push → verify → Admin stats/suggestions → live mode) must still be a screen recording of the working MVP on real data, because the submission asks for a demo of the prototype; nothing Brag renders may show invented numbers or screens. Check the result is ≤ 5 min in total.

## 5. Order and parallel waves

```text
Wave 1 (18 Oct)  WP1 DB ─────────┐   WP2 fallback   WP6 labels (draft)   WP12 admin shell/map   WP10 R4 UI   WP15 human
Wave 2 (19 Oct)  WP3 push ◄──────┤   WP4 answers ◄──┤   WP5 backfill (needs WP1+WP2; long run)   WP11 R5/RES-6
Wave 3 (20 Oct)  WP7 suggestions (WP4+WP5+WP6)   WP8 admin API (WP4+WP7)   WP9 outlook   WP13 admin pages (WP8)
Wave 4 (21 Oct)  WP14 hosting + phone E2E   bug bash   ── FEATURE FREEZE 21 Oct 23:59 ──
22 Oct           WP16 record video, build deck, README screenshots, submission checklist
23 Oct           buffer; submit by 18:00
```

- Critical path: **WP1 → WP4 → WP7 → WP8 → WP13 → WP14 → WP16**.
- Max 4–5 implementer agents at once; files are owned by one WP per wave (WP3 and WP4 both edit `api/main.py`: WP3 merges first, WP4 rebases).
- Each WP: implementer (Sonnet) in a worktree → independent reviewer → fixes → merge on APPROVE + green CI for the head SHA.

## 6. Scope guard (cut in this order if late)

1. WP9 Outlook (show MET warnings as text instead).
2. ADM-7 review queue in WP13.
3. RES-6 alert history in WP11.
4. Public hosting in WP14 (keep local API + tunnel for the video only).
5. WP6 beyond the 6 seed incidents.

Never cut: DB persistence, push on the phone, verify/report, backfill statistics and suggestions, the Admin app's map + statistics + suggestions, the video, the deck.

## 7. Risks

| Risk | Mitigation |
| --- | --- |
| Laptop sleeps or restarts (already lost 14 h on 16–17 Oct) | Power settings: never sleep on AC until 23 Oct; or move API + loggers to an always-on PC |
| Backfill over 34 months is slow | Time one month first; run in the background overnight; cache per-month results |
| Few or no news labels for BBR streets | Statistics still honest ("unverified" is not a false alarm); SUG-5 and SUG-7 work from backfill alone |
| Push blocked on iPhone | Record on Android; install guide for iPhone |
| API URL changes on restart | Tailscale Funnel keeps the machine hostname; with the Quick Tunnel fallback, redeploy Pages with the new `VITE_API_URL` |
| Funnel or tunnel bandwidth limits during judging | Static apps are served by Pages; only small JSON goes through the tunnel; the video is the required artifact |
| Usage limits stop agents mid-task | Checkpoints in memory; resume agents with SendMessage; one WP per agent |
