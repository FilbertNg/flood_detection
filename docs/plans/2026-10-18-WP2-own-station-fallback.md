# WP2 — Street own-station fallback: TDD plan

Parent: `docs/plans/2026-10-17-MVP2-remaining-mvp.md` (§3.4, WP2). Branch `fix/engine-own-station-fallback`.

**Problem.** 85 of 943 BBR streets map to river station `26558`, a JPS gauge dead since about Jul 2024. QC blanks its readings, so the streets get no river level, no ML probability and no river forecast.

**Design.**

1. Mapping format gains `wl_candidates` (ordered list). Order: stations on the street's flow path within 15 km (along-path order), then the remaining township river stations within `river_radius_km` straight-line, nearest first. `wl` stays the first candidate (backward compatible); `method`/`distance_m` describe `wl`. Old files without `wl_candidates` are read as `[wl]`.
2. `street_stations.candidates_for(mapping, street_id)` and `wl_for(mapping, street_id, dead_or_stale=None)`: first candidate not in the set; `None` if all are dead or there are none.
3. `street_stations.dead_wl(features_at_t, ids)`: a river station is dead or stale at t when its feature row at t is missing or `is_stale` (no valid QC-cleaned reading in the last `stale_after_min`). The feature rows are computed from readings at or before t only, so there is no look-ahead. The replay engine (vectorised features) and the API (`features.station_features` over the snapshot readings) both call it, so the rules, ML probability and river forecast use the same choice.
4. `replay.run`: per step, each street's river station = `wl_for(..., dead)`; the group key is `(chosen_wl, rf)`, so the rules trigger (reason text names the station via the feature row name), the ML probability (`ml_by_station[chosen_wl]`) and the forecast all follow it. If the street has candidates and all are dead: rain rules only, plus a `stale_data` reason; the level is never lowered (rain still fires). Confidence drops to `medium` (the river is blind; `low` stays `low`), and `levels.street_state` now shows the reasons whenever confidence is not `high`, so a Normal street still says why.
5. `serialize.street_detail`: the forecast uses the same choice; all candidates dead gives `river_forecast: null` (it must not fall back to the township-wide pick).
6. `scripts/build_street_stations.py`: writes `wl_candidates`; new `--data-dir` (default `<repo>/data`) so a worktree can read the archive from another path. `scripts/replay.py` gets the same `--data-dir`.

**Tests (written first, seen failing).**

- `tests/engine/test_street_stations.py`: `pick_wl_candidates` order/dedupe/radius/15 km; `candidates_for` legacy entry; `wl_for` skips dead, returns None when all dead or none; `dead_wl` on a feature frame (missing row, stale row, live row).
- `tests/engine/test_per_street.py`: street `["26558","PEKANMERU"]` with `26558` level blanked uses PEKANMERU for river rules (reason names Pekan Meru) and ML probability; all candidates blank gives rain rules still firing plus `stale_data`, level not lowered; no look-ahead (the station dies after t, so at t the first candidate is still used).
- `tests/api/`: forecast station choice in `street_detail` (fallback station, and None when all dead).
- Real-archive check: 12 Nov 2024 replay before/after, 85 streets non-null `flood_probability` at 09:00.
