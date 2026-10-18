# WP7 Suggestions SUG-1..7: TDD plan

Source: `docs/plans/2026-10-17-MVP2-remaining-mvp.md` §3.3 and WP7; rules and wording from `docs/product/prd.md` (SUG table).
The PRD table has no priority column, so priorities are derived here: **SUG-1, SUG-2, SUG-6 high; SUG-3, SUG-4, SUG-5 medium; SUG-7 low.**

## Files
- Create `floodready/stats/suggestions.py`: `suggestions(conn, date_from, date_to, tide, station_health, *, streets=None, onset_rain=None, events=None) -> list[dict]` and `station_health(readings, date_from, date_to, stations=None) -> list[dict]`.
- Create `scripts/suggestions.py`: computes for a period from the DB plus the (read-only) archive and upserts into `suggestions`.
- Create `tests/stats/test_suggestions.py`.

## Inputs and exclusions
- Alerts: `repo.list_alerts(include_replay=False, include_backfill=True)`, kind `alert` only. Replay alerts never count.
- Outcomes are recomputed here from answers with `source != 'demo'` and REAL sensor readings (`simulated = 0`), via `stats.outcomes.alert_outcome`; plus optional `news_outcomes(events, alerts)`. "Confirmed" = outcome confirmed.
- A **flood** = confirmed alerts on one street, clustered when less than 6 h apart; onset = first alert time of the cluster.
- Missed floods (SUG-6) = `missed_floods(reports, alerts)` with non-demo `report` answers.
- Onset rain (SUG-1) comes from the injected `onset_rain(street_id, onset)` (the script: highest 3 h rain sum over the street's rain gauges from QC-cleaned archive). Floods without a value are left out, never guessed.
- Tide (SUG-2): `floodready.tide.tide_at(tide, [onset])` gives hours to the nearest high water.

## Rules
| Rule | Fires when | Priority |
| --- | --- | --- |
| SUG-1 | street has >= 3 floods with known onset rain and median < 60 mm | high |
| SUG-2 | >= 2 floods with known tide and >= 70% within +-2 h of high water | high |
| SUG-3 | (a) >= 2 floods while >= 3 neighbours within 500 m of susceptibility +-1 have none; or (b) floods >= 2 x same-length window a year earlier (earlier count >= 1, this count >= 2) | medium |
| SUG-4 | >= 3 streets of susceptibility 4-5 within 30 m of each other (connected), each with >= 2 floods | medium |
| SUG-5 | >= 5 Warning/Danger alert EPISODES in the period (flapping merged, `stats/episodes.py`; cooldown 60 min) ; ranked by episodes, Danger episodes, susceptibility, street_id; top `suggestions.sug5_top_n` (10, config/rules.yaml) | medium |
| SUG-6 | >= 2 missed floods | high |
| SUG-7 | a station is stale fraction > 0.10 of the period (`stale_pct` is a 0-1 fraction) (QC-blanked or dead time counts as stale) | low |

Ids: `s_<rule>_<key>_<YYMMDD-YYMMDD>` (rule lower case without hyphen, key = street id; a 10-char hash if the id would exceed 40 chars). SUG-7 uses `street_id = "station:<graph_id>"`. The script drops `status`/`note` before `repo.upsert_suggestions`, which keeps admin decisions on re-runs.

## Tests (written first, seen failing)
1. One synthetic case per rule triggers exactly that rule with its evidence and priority (SUG-1: 35, 42, 48 mm).
2. Near-misses do not fire (2 floods for SUG-1, median 61 mm, 60% tide, 4 Warning alerts, 1 missed flood, 10% stale).
3. Empty database fires nothing.
4. Replay alerts, demo answers and simulated sensor readings never count.
5. Ids are stable across runs and <= 40 chars; text ends "Screening suggestion; site survey needed."
6. Upsert twice keeps one row and keeps status/note.
7. `station_health`: NaN, missing rows and QC-blanked time count as stale; fully valid = 0.
