# Improvement plan: data QC, ML trigger, per-street alerts, forecast, radar

16 Oct 2026 · Source: [ml-data-eda.md](../ml-data-eda.md) §6–7 and the improvement table agreed on 16 Oct.
Scope: improvements **#1–#13 and #16** (all Critical and High, Medium #8–#13, Low #16). Out of scope: #14 supervised susceptibility (waits for L1 labels), #15 tuning, #17–18 model swaps.

Execution: parallel Claude Code agents in isolated git worktrees, one work package (WP) each, supervised by the integration lead (Filbert's session). Every WP is reviewed by an independent agent before merge.

## 1. Work packages

| WP | Improvements | Owns (only these files change) | Model |
| --- | --- | --- | --- |
| **WP1 Data QC** | #2 rain QC (+ river-level QC), #7 tide gaps | `floodready/qc.py` (new), `floodready/tide.py`, `scripts/build_tide.py`, `scripts/qc_report.py` (new), `docs/data-qc-report.md` (generated); one call each in `engine/replay.py::load_archive_readings` and `live.py` | Sonnet |
| **WP2 ML features** | #8 drop features, #4 tidal-coupling feature, #9 upstream-station features | `floodready/ml/dataset.py`, `floodready/ml/network.py` (new), `scripts/build_river_network.py` (new), `config/river_network.yaml` (new); `api/runner.py::_ml_rain_ids` only | Sonnet |
| **WP3 ML training & evaluation** | #1 calibration, #4 inland headline metrics, #5 gate v2 + nested thresholds | `floodready/ml/train.py`, `floodready/ml/evaluate.py`, `scripts/train_trigger.py`, `config/ml.yaml`, `docs/evaluation-report.md` (generated) | Sonnet |
| **WP4 Terrain** | #10 FABDEM, #11 extra terrain features | `floodready/gis/terrain.py`, `scripts/build_susceptibility.py`, `scripts/fetch_fabdem.py` (new), `assets/geo/bbr_streets.geojson`, data credits | Sonnet |
| **WP5 Per-street + two-tier engine** | #3 per-street triggers, #5 engine side (ML may raise to Watch only; Watch notices) | `scripts/build_street_stations.py` (new), `assets/geo/bbr_street_stations.json` (new), `floodready/engine/*`, `floodready/ml/predict.py`, `floodready/api/*`, `config/rules.yaml`, `docs/api-contract.md`, shared types/mocks | Sonnet |
| **WP6 River-level forecast** | #12 | `floodready/ml/forecast.py` (new), `scripts/train_forecast.py` (new), `models/forecast_v1*`, `river_forecast` in `api/serialize.py`, Resident Street page + i18n, `RiverForecast` type + mocks | Sonnet |
| **WP7 Tide check** | #13 | `docs/tide-check.md` (new), optional `data/reference/` table with source | Sonnet |
| **WP8 Radar nowcast** | #16 | `floodready/radar.py` (new), radar job in `scripts/run_loggers.py`, `docs/radar-nowcast.md` (new) | Sonnet |
| **#6 Archive** | full JPS archive (~100 river stations) | running since 16 Oct (`scripts/archive_jps_history.py`) | n/a |

Reviews: one independent reviewer agent per code WP (**Opus**), fresh context, sees only the brief, the diff and the repo.

## 2. Interfaces between WPs (fixed now, so WPs can run in parallel)

- **QC (WP1):** `qc.clean_readings(readings) -> (clean_readings, flags)`, long format (`graph_id, kind, time_local, rain_15min_mm, wl_m`). Bad values become NaN, never 0. Applied inside `load_archive_readings` and the live loader, so rules, ML, API and training all see clean data.
- **Tide (WP1):** `data/interim/tide_hourly.parquet` keeps its columns, adds `tide_filled` (bool). `hours_to_high_tide` is never outside ±7 h; NaN only if no high tide can be found.
- **ML features (WP2):** `dataset.FEATURES` (new list), `dataset.build_features(readings, stations, tide, wl_ids, network=None)`, and `dataset.required_station_ids(stations, wl_ids, network=None) -> list[str]` (river stations, their upstream stations, and rain gauges within 25 km). `network.load_network(path) -> dict[str, list[str]]` (station → upstream stations).
- **Model bundle (WP3):** `bundle["model"].predict_proba(X)[:, 1]` returns a **calibrated** probability; `bundle["features"]` lists the columns. `predict.py` needs no change for calibration.
- **ML config (WP3 → WP5):** `config/ml.yaml` gains `ml_max_level: watch` (ML may raise a street to this level at most) and `p_watch` (calibrated threshold). `p_warning` is no longer used to raise levels.
- **Street → stations (WP5):** `assets/geo/<township>_street_stations.json`: `{street_id: {"wl": graph_id | null, "rf": [graph_id, ...], "method": "flow" | "nearest", "distance_m": float}}`.
- **Forecast (WP6):** `forecast.river_forecast(bundle, feats, graph_id, at) -> RiverForecast` with points at +1 h and +2 h: `wl_m` (median), `wl_m_p10`, `wl_m_p90`.

## 3. Evaluation gate v2 (pre-registered 16 Oct 2026, before any retrain on the full archive)

The EDA already looked at the current 15 stations' folds, so this gate is written **before** WP3 runs on the full archive, and it must also hold on stations the EDA never saw.

- **Signals:** `floor` = rule Watch (rain) or river at alert. `two_tier` = `floor` OR calibrated ML p ≥ θ.
- **θ** is chosen by **nested** selection: for each outer fold, on the other three folds only, take the θ with the most detections whose false alarms stay within criterion 2. Report the θ per fold; ship the median.
- **Scored on inland stations** (tidal = data-driven: lag-25 autocorrelation of level < −0.2, see the EDA). Detected = fired 15 min–3 h before a crossing; false alarm = alarm with no crossing within 3 h.
- **Pass if all hold:**
  1. median lead of `two_tier` ≥ median lead of `floor` + 30 min;
  2. false alarms per station-month of `two_tier` ≤ 1.5 × `floor`'s;
  3. on the **fresh stations** (river stations first archived after 16 Oct 2026), criteria 1–2 also hold if they have ≥ 30 inland crossings; otherwise they are reported, not gating.
- **Pass:** `ml_drives_alerts: true`, `ml_max_level: watch`. **Fail:** ML stays informational. In both cases Warning and Danger come only from the JPS rules.

## 4. QC protocol (every code WP)

1. **TDD:** failing test first. Tests use real fixtures where possible.
2. **Full suite green:** `pytest -q` and, if web files changed, `pnpm -r test`, typecheck and build.
3. **Evidence in the PR:** commands run and their output, before/after metrics, counts of affected rows. "Should work" is not evidence.
4. **Rules checked by the reviewer:** no fabricated data; features use only data at or before t; no period scored by a model that trained on it; ML never lowers an official threshold; contract changes labelled `contract` with types, mocks and api-contract.md updated; no secrets; data credits.
5. **Independent review** (Opus): reads the brief and the diff, re-runs the tests, tries to break it (edge cases: empty data, NaN, stale stations, tide gaps, a street with no station). Verdict: approve, or a numbered list of required fixes. Fixes go back to the same implementer.
6. **Integration (lead):** merge order WP1 → WP2 → WP3 → WP4 → WP5 → WP6 → WP8 (WP7 any time). After all merge: retrain on the full archive, regenerate the evaluation report, replay 12 Nov 2024 in the API and the Resident app, compare before/after.

## 5. Acceptance (whole plan)

- `docs/data-qc-report.md` lists every flagged reading by rule and station; 12 Nov 2024 storm readings untouched.
- Evaluation report: inland headline, tidal and pooled sections, calibration table (reliability and Brier score), gate v2 verdict with per-fold θ.
- 12 Nov 2024 replay at 09:00: the memorandum streets still at Warning; fewer streets alerting than the township-wide ~40%; each street shows its own stations.
- Street page shows a river-level forecast with a range.
- Radar: a documented feasibility verdict; if feasible, frames archived and a radar reason shown, informational only.
- `docs/tide-check.md`: Open-Meteo vs an official or independent tide prediction for 12 Nov 2024, with sources.
