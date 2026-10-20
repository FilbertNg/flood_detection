# WP5 Backfill 2024-2026 (BBR) TDD plan

Parent: `docs/plans/2026-10-17-MVP2-remaining-mvp.md` WP5. Branch `feat/backfill`.

## Design

- `floodready/engine/backfill.py: run_backfill(start, end, township_id, engine, step=15 min, *, data_dir=None, models_dir=None, readings=None, stations=None, tide=None, mapping=None) -> dict[str, int]` returns alert rows inserted per month (`"YYYY-MM"`). The keyword arguments only inject data for tests; the script passes `data_dir`.
- Month by month. Per month: load readings (`replay.load_archive_readings`, from 5 days before the month for the features; QC runs on each gauge's full archive history, which covers `qc.QC_HISTORY_DAYS = 120`), take the out-of-fold model for the month (`predict.bundle_for(..., live=False)`), run `replay.run`, then `repo.replace_backfill` for the month and `repo.insert_alerts(..., is_backfill=True, is_replay=False)`.
- Honest ML: a calendar month sits inside one quarter, so one fold model per month. The model must be `out_of_sample`, its sidecar json `excluded_fold` must equal `dataset.fold_of(month)`, and every step asserts `fold_of(t)` equals that fold, else `RuntimeError`. Probabilities are display-only (`ml_drives_alerts: false`).
- Writes only alerts, never `street_state`. State (previous levels, last alerts) restarts at each month start, so an alert open across midnight of the 1st is re-issued on the 1st (documented limitation).
- `replace_backfill` is clipped to `[start, end + step)`, so a partial range never deletes rows outside it.

## Tests (`tests/engine/test_backfill.py`, written first, seen failing)

1. Equivalence: 12 Nov 2024 06:00-14:00 on the committed real fixtures gives the same (street, level, kind, issued_at) as `replay.run`; rows flagged `is_backfill`, ids end `~backfill`.
2. Re-running replaces, not duplicates; other months untouched; no `street_state` rows.
3. Fold: `oof_bundle` returns the model excluding the month's fold; a mismatch or the final model raises; the per-step assertion fires on a wrong fold.
4. `_months` splits a range at month boundaries.

## Real run

`scripts/backfill.py --from 2024-11-01 --to 2024-11-30 --db sqlite:///<worktree>/backfill_test.db --data-dir <archive>`; time it; extrapolate to 2024-01-01 to 2026-10-17.
