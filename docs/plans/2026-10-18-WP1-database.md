# WP1 Database layer (F3) Implementation Plan

> Expands WP1 of `docs/plans/2026-10-17-MVP2-remaining-mvp.md`. Interface: §3.1 (names and signatures exact). Tables: build plan §4.3.

**Goal:** SQLAlchemy 2 Core schema + repository (SQLite for the demo, Postgres-compatible). The runner and API are NOT wired to it here (WP3).

**Design notes**
- Portable types only: `String/Text/Float/Integer/Boolean/DateTime`; `*_json` columns are TEXT holding `json.dumps`; datetimes are naive MYT; API dicts re-attach `+08:00`.
- `alert_id` = `<street>@<YYYYmmddTHHMM>-<kind>` (same as the runner today); replay rows get a `~replay`, backfill rows a `~backfill` suffix so the three modes never collide on the primary key. Inserting an existing id is a no-op (idempotent for WP3 restarts).
- `active` alert = latest alert of a street (by `issued_at`) that is `kind='alert'` and (`window_end >= now` or `issued_at + cooldown_min >= now`), `now = floodready.jobs.now_myt()` (monkeypatched in tests), cooldown 60 min (config/rules.yaml).
- `get_street_states(township_id)` filters by the street id prefix `<township_id>-` (street ids are `<TOWNSHIP>-<slug>`), so no `streets` rows are needed.
- `delete_device` also removes `answers.photo_path` files from disk (missing file ignored).
- Duplicate answers: unique index on `(device_id, alert_id)`; NULL alert_id (reports) is never a duplicate. Violations raise `DuplicateAnswer`.

**Files:** `floodready/db/{__init__,schema,repo}.py`, `scripts/db_init.py`, `tests/db/test_repo.py`, `pyproject.toml` (`sqlalchemy>=2` in `api`; `postgres = ["psycopg[binary]>=3.1"]`).

## Tasks (each: write test, see it fail, implement, pass)

- [ ] 1. Deps + `schema.py` + `connect`; tests `test_postgres_types`, `test_connect_creates_tables`.
- [ ] 2. `save_street_states`/`get_street_states`; `test_states_round_trip` (all fields unchanged; second save replaces; mode and township isolation).
- [ ] 3. `insert_alerts`/`list_alerts`; `test_alert_ids_and_flags` (unique ids, replay excluded, active rule, since, street filter, AlertSummary shape).
- [ ] 4. `insert_answer`/`list_answers`/`set_answer_review`; `test_duplicate_answer` (reports with NULL alert_id both stored; review filter).
- [ ] 5. `upsert_subscription`/`list_subscribers`/`delete_device`; `test_delete_device` (rows + photo files; other devices untouched).
- [ ] 6. `insert_sensor_reading`, `upsert_suggestions`, `update_suggestion`, `insert_note`.
- [ ] 7. `scripts/db_init.py --url`; test creates a file DB and inspects its tables.
- [ ] 8. Full suite, commit, push, PR.
