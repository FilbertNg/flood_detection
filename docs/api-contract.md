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
- **Per-street triggers:** each street's level comes from its own stations only (`StreetDetail.stations`, river station first: the one its flow path reaches within 15 km, else the nearest within 5 km; plus the rain gauges within 5 km, else the nearest two), not from every station in the township. A street with no river station is judged on its rain gauges alone. `assets/geo/<township>_street_stations.json` holds the mapping; without it every street gets the township-wide trigger.
- **Two-tier ML:** ML may raise a street's trigger to `watch` at most (`ml_max_level`) and only while `ml_drives_alerts` is true; `warning` and `danger` come only from the JPS rules, and ML never lowers a rule level. `flood_probability` is the probability for the street's own river station (null when it has none).
- **Alerts:** `GET /alerts` and `StreetDetail.history` now include `watch` alerts (`alerts.alert_levels` in `config/rules.yaml` is `[watch, warning, danger]`). A rising level re-alerts inside the cooldown.
- **IDs:** `street_id` = `<TOWNSHIP_ID>-<slug>` (e.g. `BBR-jalan-makyong`); `township_id` from `config/townships.yaml`; `graph_id` = JPS Infobanjir station ID (e.g. `26558`, `PEKANMERU`).
- **Errors:** `{"detail": "..."}` (FastAPI default) with 400 (invalid input), 401 (missing or invalid token), 404 (unknown ID), 409 (duplicate answer), 422 (validation).
- **Admin auth:** `Authorization: Bearer <token>` from `POST /admin/login`.
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
| `GET /admin/stats?from=&to=` | JWT | ISO dates | `Stats` |
| `GET /admin/report?month=YYYY-MM` | JWT | — | `Report` |
| `GET /admin/suggestions?from=&to=` | JWT | — | `Suggestion[]` |
| `PATCH /admin/suggestions/{id}` | JWT | `SuggestionUpdate` | `Suggestion` |
| `GET /admin/answers?review_status=pending` | JWT | — | `Answer[]` |
| `PATCH /admin/answers/{answer_id}` | JWT | `AnswerReview` | `Answer` |
| `POST /admin/notes` | JWT | `OpsNoteRequest` | 204 |
| `POST /admin/replay` | JWT | `ReplayRequest` | `Status` |
| `DELETE /admin/replay` | JWT | — | `Status` (back to live) |

**Web Push payload** (every notification): `PushPayload` = `{title, body, url, alert_id, level}`; `url` is the app path to open, e.g. `/street/BBR-jalan-makyong`. Replay alerts start the title with `[Replay]`.

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
