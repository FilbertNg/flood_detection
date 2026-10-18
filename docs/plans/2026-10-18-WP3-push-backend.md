# WP3 Web Push backend: TDD plan

Parent: `docs/plans/2026-10-17-MVP2-remaining-mvp.md` (WP3, §3.1, §3.2). Branch `feat/push-backend`.

## Design

- `Runner(ctx, db=None, push=None)`: `db` is a SQLAlchemy engine (default in-memory SQLite). `_record` saves street states (`mode` live or replay) and alerts (`insert_alerts`, `is_replay`) in one transaction; the in-memory alert log is gone. `snapshot().alerts`, `GET /alerts` and `StreetDetail.history/active_alert` read `repo.list_alerts`, so a restart keeps alerts.
- `repo.clear_replay(conn)` deletes replay-mode alerts and street states. `start_replay` and `stop_replay` call it, so each rehearsal issues and pushes alerts again.
- Only ids returned as NEW by `insert_alerts` go to push, and only when the summary has `push: true` (levels from `alerts.push_levels`, never all-clear). After a restart the ids already exist, so nothing is new and nothing is pushed.
- `floodready/push.py`: `payload()` (exact `PushPayload`, EN/MS, `[Replay] ` prefix, `url=/street/<id>`), `notify(conn, alert, street_name, send)` (sends to `list_subscribers(street_id)`; 404/410 deletes only that subscription; other errors are logged), `PushService` (VAPID from env, one worker thread so the tick and the API never wait on the push service; `flush()` for tests). Missing keys: disabled, one warning.
- API: `GET /push/public-key` (503 when disabled), `POST /subscriptions` (204, unknown street 400), `DELETE /subscriptions/{device_id}` (`repo.delete_device` in a transaction, `repo.remove_files` after commit, 204). Route blocks are separate in `main.py`.
- `scripts/gen_vapid.py` writes keys into `.env` (gitignored); `.env.example` documents the variables.

## Tests (written first, seen failing)

1. `tests/db/test_clear_replay.py`: clear_replay removes replay alerts and states only.
2. `tests/test_push.py`: payload shape, EN/MS, `[Replay]`; notify only to that street's subscribers in their language; 404/410 deletes the subscription, other errors are logged and the rest still get sent; disabled service warns once.
3. `tests/api/test_subscriptions.py`: public key / 503; subscribe stores device and streets; unknown street 400; delete 204 removes rows and photo files after commit.
4. `tests/api/test_runner_persistence.py`: states and alerts are in the DB; a new Runner on the same DB file sees the alerts and does not re-push; all-clears not pushed; replay pushes with `[Replay]`; two replays in a row both push; GET /alerts reads the DB.
