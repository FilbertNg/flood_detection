# API contract (v1)

The contract between the engine/API (Python) and the two apps (TypeScript). It is frozen at M0: changing it needs a PR labelled `contract`, approved by one backend and one frontend owner, with the mocks updated (build plan §9).

**Source of truth**

| What | File |
| --- | --- |
| Request and response shapes | [`packages/shared/src/api/types.ts`](../packages/shared/src/api/types.ts) |
| One example per endpoint (UI development) | [`packages/shared/src/mocks/index.ts`](../packages/shared/src/mocks/index.ts) |
| Engine records (Python) | [`floodready/engine/types.py`](../floodready/engine/types.py) |
| Rule thresholds, risk matrix, ML settings | [`config/rules.yaml`](../config/rules.yaml), [`config/risk_matrix.yaml`](../config/risk_matrix.yaml), [`config/ml.yaml`](../config/ml.yaml) |

`tests/engine/test_types.py` fails if the Python and TypeScript level names drift apart; `tsc` fails if a mock no longer matches the types.

## Conventions

- **Base path:** `/api/v1`. JSON everywhere except `POST /answers` (multipart/form-data, because of the photo).
- **Times:** ISO 8601 with offset, MYT: `2024-11-12T09:00:00+08:00`. Dates: `2024-11-12`.
- **Levels:** `normal` < `watch` < `warning` < `danger` (lowercase).
- **Per-street triggers:** each street's level comes from its own stations only (`StreetDetail.stations`, river station first: the one its flow path reaches within 15 km, else the nearest within `river_radius_km` (10 km); plus the rain gauges within `rain_radius_km` (10 km), at least `min_rain_gauges` (2), all in `config/rules.yaml`; ids de-duplicated), not from every station in the township. A street with no river station is judged on its rain gauges alone. `assets/geo/<township>_street_stations.json` holds the mapping; without it every street gets the township-wide trigger.
- **Two-tier ML:** ML may raise a street's trigger to `watch` at most (`ml_max_level`) and only while `ml_drives_alerts` is true; `warning` and `danger` come only from the JPS rules, and ML never lowers a rule level. `flood_probability` is the probability for the street's own river station (null when it has none).
- **Alerts:** `GET /alerts` and `StreetDetail.history` now include `watch` alerts (`alerts.alert_levels` in `config/rules.yaml` is `[watch, warning, danger]`). A rising level re-alerts inside the cooldown. Each alert has `push: boolean` (level in `alerts.push_levels`; since 17 Oct 2026 `[watch, warning, danger]`, so Watch is pushed too); all-clears have `push: false`. The nowcast `window` is set only from `alerts.window_from` (default `warning`), so Watch streets have `window: null`. The all-clear is held until the alert is `alerts.clear_after_min` (60 min) old; until then the alert stays in `active` (`GET /alerts?active=true`, `StreetDetail.active_alert`) even if the street reads Normal, and a level that returns inside the hold is not re-pushed. Behaviour only: no field or shape changes.
- **IDs:** `street_id` = `<TOWNSHIP_ID>-<slug>` (e.g. `BBR-jalan-makyong`); `township_id` from `config/townships.yaml`; `graph_id` = JPS Infobanjir station ID (e.g. `26558`, `PEKANMERU`).
- **Errors:** `{"detail": "..."}` (FastAPI default) with 400 (invalid input), 401 (missing or invalid token), 404 (unknown ID), 409 (duplicate answer), 422 (validation).
- **Admin auth:** `Authorization: Bearer <token>` from `POST /admin/login`, or a read-only preview token from `POST /admin/preview` (only while the API has `ADMIN_PREVIEW=1`; 404 otherwise). A preview token has viewer rights and gets 403 on `GET /admin/answers`.
- **Sensor auth:** `Authorization: Bearer <SENSOR_TOKEN>`.
- **CORS:** the two app origins listed in the API's `CORS_ORIGINS` env var.
- **Reason codes** (`StreetDetail.reasons[].code`): `rain_1h`, `rain_2to4h`, `river_level`, `ml_probability`, `tide_high`, `forecast_rain`, `met_warning`, `stale_data`, and `radar_approaching` (unit `min`, `value` = estimated minutes until a rain cell arrives; **informational only, it never changes `level`**, see [radar-nowcast.md](radar-nowcast.md)). It appears only in live mode and only while the radar logger is running.
- **Replay and demo data** carry `is_replay: true` / `source: "demo"`; statistics never include them.

## Endpoints

| Method + path | Auth | Request | Response (types.ts) |
| --- | --- | --- | --- |
| `GET /status` | — | — | `Status` |
| `GET /streets?township=BBR` | — | — | `StreetCollection` (GeoJSON) |
| `GET /streets/{street_id}` | — | — | `StreetDetail` |
| `GET /stations?township=BBR` | — | — | `Station[]` |
| `GET /stations/{graph_id}/series?from=&to=` | — | ISO times | `SeriesPoint[]` |
| `GET /alerts?street_id=&active=true` | — | — | `AlertSummary[]` |
| `GET /push/public-key` | — | — | `PushPublicKey` |
| `POST /subscriptions` | — | `SubscriptionRequest` | 204 |
| `DELETE /subscriptions/{device_id}` | — | — | 204 (deletes all data for that device) |
| `POST /answers` | — | `AnswerForm` (multipart) | `AnswerCreated`; 409 if this device already answered this alert |
| `POST /sensor/readings` | sensor token | `SensorReading` | 204 |
| `POST /admin/login` | — | `LoginRequest` | `LoginResponse` |
| `POST /admin/preview` | — | — | `LoginResponse` (read-only preview; 404 when `ADMIN_PREVIEW` is off, 503 without `JWT_SECRET`) |
| `GET /admin/stats?from=&to=` | JWT | ISO dates | `Stats` |
| `GET /admin/report?month=YYYY-MM` | JWT | — | `Report` |
| `GET /admin/suggestions?from=&to=` | JWT | — | `Suggestion[]` |
| `PATCH /admin/suggestions/{id}` | JWT | `SuggestionUpdate` | `Suggestion` |
| `GET /admin/answers?review_status=pending` | JWT | — | `Answer[]` |
| `PATCH /admin/answers/{answer_id}` | JWT | `AnswerReview` | `Answer` |
| `POST /admin/notes` | JWT | `OpsNoteRequest` | 204 |
| `POST /admin/replay` | JWT | `ReplayRequest` | `Status` |
| `DELETE /admin/replay` | JWT | — | `Status` (back to live) |

**Subscription validation** (`POST /subscriptions` and `DELETE /subscriptions/{device_id}`, 422 otherwise; added with WP3, PR #46): `device_id` matches `^[A-Za-z0-9_-]{16,64}$` (the Resident app generates it with `crypto.randomUUID()`, falling back to `crypto.getRandomValues`; ids from earlier app versions, `dev_` + base36, already match); `subscription.endpoint` is an `https` URL on a push-service host (`fcm.googleapis.com`, `updates.push.services.mozilla.com`, `*.notify.windows.com`, `web.push.apple.com`, `*.push.apple.com`); `keys` has only `p256dh` (≤ 128 chars) and `auth` (≤ 64), base64url; unknown street ids give 400. With no VAPID keys on the server, `GET /push/public-key` returns 503. No response shape changes.

**Web Push payload** (every notification): `PushPayload` = `{title, body, url, alert_id, level}`; `url` is the app path to open, e.g. `/street/BBR-jalan-makyong`. Replay alerts start the title with `[Replay]`.

**Tide** (`StreetDetail.tide`): hourly points `{time, height_m, filled}` from the issue time to +12 h. `filled` (boolean, additive) is `true` when that hour was gap-filled by the harmonic fit (`tide_filled` in the tide table, see `floodready/tide.py`) and is not Open-Meteo data; `false` for source data, and for a tide table that has no `tide_filled` column. Clients may ignore it; to be honest on screen, mark or dash-style filled hours.

**River forecast** (`StreetDetail.river_forecast`, `RiverForecast`): the level of one river station at +1 h and +2 h, or `null` when there is no model, the model cannot be applied, or the station has no level at most 30 min old. Fields: `graph_id`, `name` (station name), `wl_now_m` (latest observed level, m), `wl_now_time` (when it was read; at most 30 min before `data_time`), `warning_m` (the station's own JPS warning level, for reference; may be `null`), and `points[]` = `{time, wl_m (median), wl_m_p10, wl_m_p90}` in metres with `wl_m_p10 <= wl_m <= wl_m_p90`. The station is the street's own river station (`street_stations` mapping, see Per-street triggers above). Only a street with no river station of its own gets the township river station with a fresh level closest to its warning level. In replay it comes from the fold model that never trained on that period.

## Mocks

`@floodready/shared/mocks` exports one typed example per endpoint (`status`, `streets`, `streetDetail`, `alerts`, `stations`, `rainSeries26558`, `levelSeriesPekanMeru`, `stats`, `report`, `suggestions`, `pendingAnswers`).
- The station readings are real 12 Nov 2024 JPS values; everything else is illustrative.
- Apps must show a **"Mock data" ribbon** whenever they use mocks.
- Mock screens must never appear in the deck or the video.

## Check the contract locally

```bash
.venv/Scripts/python.exe -m pytest -q tests/engine          # Python side + level-name parity
cd packages/shared && npx -p typescript@5.6.3 tsc -p .       # TS types + mocks (pnpm typecheck after F2)
```
