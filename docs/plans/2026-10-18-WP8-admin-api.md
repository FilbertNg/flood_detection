# WP8 — Admin endpoints (B5): TDD plan

Parent: `2026-10-17-MVP2-remaining-mvp.md` §3.1, §3.3, WP8. Contract: `docs/api-contract.md`, `packages/shared/src/api/types.ts`. PRD ADM-1..7.

## Design decisions

1. **Auth** (`floodready/api/auth.py`). `admin_users` (email, bcrypt hash, role `admin|viewer`). JWT HS256, `exp` 12 h, claims `sub`, `role`; decoding pins the algorithm and requires `exp` and `sub`. A token without a role is a viewer. Reads (`GET`) need any valid token; every write (`PATCH`, `POST /admin/notes`, `POST/DELETE /admin/replay`) needs `admin` (viewer gets 403). Unknown user and wrong password take the same path (a dummy bcrypt check) and both give 401.
2. **Login sources**, in order: `admin_users`; the `ADMIN_EMAIL` / `ADMIN_PASSWORD` environment pair (admin role, constant-time compare; kept because the earlier API tests and the demo script use it); the development login only while `ADMIN_EMAIL`, `ADMIN_PASSWORD` and `JWT_SECRET` are all unset **and** `admin_users` is empty, with a loud warning at start-up and on every dev login. If `JWT_SECRET` is unset outside development mode, login answers 503 and tokens are never accepted. `scripts/seed_admin.py` creates or updates a user from `--email/--role` and a password from `--password` or `ADMIN_PASSWORD` (prompt if neither); nothing is committed.
3. **Statistics** (`floodready/stats/statistics.py`) are pure functions over the database and plain inputs. Alerts: `list_alerts(include_backfill=True, include_replay=False, count_simulated_sensor=False)` with demo answers ignored (`exclude_demo=True`, a new keyword of `repo.outcomes_for/list_alerts`), statistics count EPISODES, not rows (the engine flaps): per street, an alert row through to the next all-clear (or the end of the data); a new alert within `alerts.cooldown_min` of the previous all-clear reopens the same episode; level = highest reached; an episode counts in the period of its start; outcome = best of its rows (confirmed > not_confirmed > unverified), so the confirmation rate is per episode. `kpis.alerts` = episodes; additive extras `alert_rows` (raw rows), `by_level`, `street_days_with_alert` (types.ts, optional). Outcome = resident/sensor outcome, or `confirmed` when a labelled news event matches (`news_outcomes`).
   - `confirmation_rate = confirmed / (confirmed + not_confirmed)`; the `Stats` type is `number` (not null), so it is `0` when both are 0 and the UI shows n/a from the counts.
   - `missed_floods`: `missed_floods(reports, alerts)` over non-demo, non-spam reports and all non-replay alerts, first report in the period.
   - A *flood* is a distinct (street, date) with a confirmed alert or a news event (`flooded == 1`, street known). Its onset is the news `start_time_local` (minute/hour precision) else the earliest real `yes` answer of the confirmed alert; no time, no lead and no rain figure.
   - `median_lead_min`: median over floods with an onset of (onset − first alert on that street within the previous 6 h) in minutes; floods with no earlier alert are skipped; `null` when none.
   - `rain_at_onset`: from the floods with an onset only: the largest 2 h / 3 h / 4 h rain sum ending at the onset (as the engine's `rain_2to4h`), maximum over the street's rain gauges.
   - `by_week` ISO week `YYYY-Www`, only weeks with alerts. `by_street` names from the streets file, sorted by floods, then alerts.
   - `sources`: `outcomes_from_news` = alerts confirmed only by news; `outcomes_from_residents` = alerts whose resident/sensor outcome is not `unverified`.
   - `station_health`: `stale_pct` (fraction 0..1) = share of expected 15-min slots in the period (up to now) without a value, worst of the station's rain and level series. Stations come from the township's station list.
4. **Report** (`floodready/stats/report.py`): `stats` for the calendar month → `summary`, `top_streets` (first 5), `data_health`; `events` = labelled news events of the month plus resident-confirmed floods not already in them; `suggestions` of the month from the table.
5. **Endpoints** live in `floodready/api/admin.py` (`install(app, ...)`, one call in `create_app`): `POST /admin/login`, `GET /admin/stats`, `GET /admin/report`, `GET/PATCH /admin/suggestions`, `GET/PATCH /admin/answers`, `POST /admin/notes`; `GET /uploads/<name>` serves resident photos read-only (name pattern `uuid.jpg`, resolved inside `UPLOADS_DIR`, no listing, `nosniff`). Suggestion text always ends "Screening suggestion; site survey needed." (appended on read). `photo_path` → `photo_url`. Review accepts `valid|spam` only. The events file is `EVENTS_CSV` (default `data/events/events.csv`; absent is fine).
6. WP7 owns `suggestions` rows; this WP only reads and updates them.

## Tasks (failing test first)

1. `tests/api/test_admin_auth.py`: wrong password 401; unknown user 401; every `/admin/*` without a token 401; bad / expired / wrong-algorithm token 401; viewer GET 200 and PATCH/POST 403; dev login only when all unset and no users; JWT_SECRET missing → 503.
2. `tests/stats/test_statistics.py`: seeded DB with hand-computed KPIs, weeks, streets, lead, rain at onset, sources; excluded rows (replay alert, demo answers, simulated sensor) change nothing; station health 26558 blanked → 1.0; empty period.
3. `tests/stats/test_report.py`: 2024-11 lists the 12 Nov 2024 event, summary equals month stats.
4. `tests/api/test_admin.py`: stats/report/suggestions/answers/notes/uploads endpoints, validation, photo_url, author from the JWT, path traversal.
5. Implement; `scripts/seed_admin.py` with a test; docs (`HANDOFF.md`, `.env.example`); full suite.
6. Fix `2026-10-18-WP4-answers-outcomes.md` §3 and §7 to the merged rules.
