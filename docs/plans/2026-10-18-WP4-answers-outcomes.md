# WP4 — Answers, reports, sensor, outcomes (B4): TDD plan

Parent: `2026-10-17-MVP2-remaining-mvp.md` §3.3 and WP4. Rules: PRD "Live benchmark".

## Design decisions

1. **Outcome rules** (`floodready/stats/outcomes.py`, pure functions). Answers are deduplicated per device; `spam` rows, `not_sure` and `report` are ignored for scoring; only answers within 3 h after the alert's `issued_at` count. A "yes" or "no" from more than 1 km from the street centroid weighs 0.5. confirmed = sensor above threshold, or yes-weight >= 2, or a nearby yes with a photo; not_confirmed = no-weight >= 3 and no yes at all; otherwise unverified (never a false alarm).
2. **Distance** is computed server-side at insert from the street centroid in the loaded streets data (haversine on the unrounded client lat/lon, stored as `distance_m`); lat/lon are then rounded to 3 decimals before storage. No location given: distance unknown, weight 1.
3. **Sensor**: `config/rules.yaml` `sensor.threshold_cm`. The MVP has one sensor, so a reading above the threshold confirms every alert of its township issued within the previous 3 h (the alert must be issued before the reading). Simulated readings are stored with `simulated=true`, count toward the live outcome (labelled in the apps), and are excluded from statistics via `list_alerts(count_simulated_sensor=False)`.
4. **Replay alerts**: answers to a replay alert are stored with `source='demo'`. Statistics exclude `source='demo'` answers and `is_replay` alerts.
5. **Confirmed push**: the router takes `on_alert_confirmed(alert)`; it is called exactly once, when an answer or sensor reading moves an alert to confirmed. Default is a logging no-op; WP3 wires `push.notify`.
6. **Photos**: Pillow re-encodes pixels only (new image, no metadata), saved as `<uuid4>.jpg` under `UPLOADS_DIR`. <= 10 MB, `image/*`, must decode.
7. Routes live in `floodready/api/answers.py` (`install(app, ...)`), one call in `create_app`, to ease the WP3 rebase. The DB engine is passed to `create_app(engine=...)`; `app.py` builds it from `DATABASE_URL`.

## Tasks (each: failing test, run, implement, run)

1. `tests/stats/test_outcomes.py`: alert_outcome rules (2 yes, 1 yes + photo, 3 no, mixed yes/no, no answers, sensor, far half weight, window, spam, device dedupe); missed_floods; news_outcomes.
2. `tests/db/test_outcomes_repo.py`: `list_alerts` computes outcome; simulated sensor toggle.
3. `tests/api/test_answers.py`: POST /answers validation (street, alert belongs, enums, 10 MB, non-image), 3-decimal rounding, EXIF stripped, random filename, 409, demo source for replay alerts, hook once, sensor token 401/204; `sim_sensor` posts simulated readings.
4. Implement, add Pillow + python-multipart to the `api` extra, run the full suite, open PR.

## Review round 1 changes (PR #47)

Sensors are mapped to streets in `config/rules.yaml` (`sensor.devices`; sim-1 on BBR-jalan-makyong-1-ku5), unknown devices get 422. Simulated readings never affect live alerts; they confirm only replay alerts of the mapped street (no window). Image decoding is limited to JPEG/PNG/WEBP (MPO phone files open through the JPEG plugin) with a 40 MP cap. Also: body-size middleware (413), per-IP rate limit (10/min), backfill alerts rejected, replay-mode reports stored as demo, bare file name in photo_path, bounded level_cm, 409 on a duplicate reading, active-Warning check for missed floods, push hook only when a confirming device is subscribed to the street.
