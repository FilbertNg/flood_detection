"""Repository over the database tables (build plan §4.3; WP1 interface §3.1).

SQLAlchemy 2 Core only. Callers pass a Connection (e.g. `with engine.begin() as conn`) and own the transaction.
Datetimes are stored naive MYT and returned as ISO 8601 with +08:00.
"""
from __future__ import annotations

import json
import os
import uuid
from functools import lru_cache
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

import yaml
from sqlalchemy import Engine, and_, bindparam, create_engine, delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from ..engine.alerts import clear_after as alert_clear_after
from ..engine.outlook import pushes as outlook_pushes
from ..engine.types import Alert, Level, Reason, StreetState
from ..jobs import now_myt
from ..stats import outcomes
from . import schema as t

# Single-writer assumption: the API process is the only writer (build plan decision 2). The delete/select-then-insert
# upserts below are not safe against two concurrent writers on Postgres (PK races); add ON CONFLICT if that changes.

ROOT = Path(__file__).resolve().parents[2]
_CHUNK = 400


@lru_cache(maxsize=1)
def _alerts_cfg() -> dict:
    """`alerts:` block of config/rules.yaml: the single source of truth for push levels."""
    with open(ROOT / "config" / "rules.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["alerts"]


def _sensor_cfg() -> dict:
    with open(ROOT / "config" / "rules.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["sensor"]


def sensor_threshold_cm() -> float:
    """`sensor.threshold_cm` of config/rules.yaml: a reading above it confirms the alerts of the sensor's streets."""
    return float(_sensor_cfg()["threshold_cm"])


def sensor_devices() -> dict[str, set[str]]:
    """`sensor.devices` of config/rules.yaml: device_id -> the street ids that sensor speaks for. Readings of a
    device confirm only alerts on these streets; unknown devices are rejected by the API."""
    return {d: set(v.get("street_ids", [])) for d, v in (_sensor_cfg().get("devices") or {}).items()}


def push_levels() -> tuple[str, ...]:
    return tuple(_alerts_cfg().get("push_levels", ["watch", "warning", "danger"]))


def uploads_dir() -> Path:
    """Directory resident photos live in (env UPLOADS_DIR, default <repo>/data/uploads)."""
    return Path(os.environ.get("UPLOADS_DIR", ROOT / "data" / "uploads"))


class DuplicateAnswer(Exception):
    """A device already answered this alert."""


# ---------- helpers ----------

def _iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.strftime("%Y-%m-%dT%H:%M:%S") + "+08:00"


def _naive(dt: datetime | str | None) -> datetime | None:
    """Accept datetimes or ISO strings (with or without offset); store naive MYT."""
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
    return dt


def _window(start: datetime | None, end: datetime | None) -> dict | None:
    return {"start": _iso(start), "end": _iso(end)} if start else None


def _reason_dict(r) -> dict:
    return {"code": r.code, "value": r.value, "unit": r.unit, "station": r.station,
            "text": {"en": r.text_en, "ms": r.text_ms}}


def _chunks(items: list, n: int = _CHUNK):
    for i in range(0, len(items), n):
        yield items[i:i + n]


# ---------- connection ----------

def connect(url: str) -> Engine:
    """Create the engine and any missing tables. `sqlite://` (in memory) shares one connection."""
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")   # psycopg 3 (the `postgres` extra), not psycopg2
    kwargs: dict = {}
    if url in ("sqlite://", "sqlite:///:memory:"):
        kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    elif url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
    engine = create_engine(url, **kwargs)
    t.metadata.create_all(engine)
    return engine


# ---------- street states ----------

def save_street_states(conn, states: list[StreetState], mode: str) -> None:
    now = now_myt()
    rows = [{
        "street_id": s.street_id, "mode": mode, "level": s.level.json, "trigger_level": s.trigger_level.json,
        "confidence": s.confidence, "flood_probability": s.flood_probability,
        "fired_by_json": json.dumps(list(s.fired_by)), "window_start": s.window_start, "window_end": s.window_end,
        "reasons_json": json.dumps([_reason_dict(r) for r in s.reasons]), "data_time": s.data_time, "updated_at": now,
    } for s in states]
    if not rows:
        return
    conn.execute(delete(t.street_state).where(and_(t.street_state.c.street_id == bindparam("b_street"),
                                                   t.street_state.c.mode == bindparam("b_mode"))),
                 [{"b_street": r["street_id"], "b_mode": mode} for r in rows])
    conn.execute(insert(t.street_state), rows)


def clear_replay(conn, *, uploads: Path | str | None = None) -> list[Path]:
    """Delete replay-mode alerts and street states so a new replay starts clean and re-issues (and re-pushes) its alerts.
    Also deletes the demo answers (source='demo': answers to replay alerts and reports sent during a replay, so the same
    demo device can answer again) and the simulated sensor readings that score replay alerts.
    Live and backfill rows, resident answers and real sensor readings are untouched.

    Returns the demo photo files to remove (inside the uploads directory only); the caller unlinks them with
    `remove_files` AFTER its transaction commits."""
    root = Path(uploads or uploads_dir()).resolve()
    photos = [p for (p,) in conn.execute(select(t.answers.c.photo_path).where(
        t.answers.c.source == "demo", t.answers.c.photo_path.is_not(None)))]
    conn.execute(delete(t.answers).where(t.answers.c.source == "demo"))
    conn.execute(delete(t.sensor_readings).where(t.sensor_readings.c.simulated.is_(True)))
    conn.execute(delete(t.alerts).where(t.alerts.c.is_replay.is_(True), t.alerts.c.is_backfill.is_(False)))
    conn.execute(delete(t.street_state).where(t.street_state.c.mode == "replay"))
    safe = []
    for p in photos:
        path = (root / p).resolve()
        if path != root and path.is_relative_to(root):
            safe.append(path)
    return safe


def get_street_states(conn, township_id: str, mode: str) -> list[dict]:
    """States of one township; street ids are `<TOWNSHIP>-<slug>`, so the prefix selects the township."""
    q = select(t.street_state).where(t.street_state.c.mode == mode,
                                     t.street_state.c.street_id.startswith(f"{township_id}-", autoescape=True)).order_by(t.street_state.c.street_id)
    return [{
        "street_id": r.street_id, "mode": r.mode, "level": r.level, "trigger_level": r.trigger_level,
        "confidence": r.confidence, "flood_probability": r.flood_probability,
        "fired_by": json.loads(r.fired_by_json or "[]"), "window": _window(r.window_start, r.window_end),
        "reasons": json.loads(r.reasons_json or "[]"), "data_time": _iso(r.data_time), "updated_at": _iso(r.updated_at),
    } for r in conn.execute(q)]


# ---------- alerts ----------

def _alert_id(a: Alert, is_replay: bool, is_backfill: bool, horizon: str) -> str:
    """Live nowcast ids equal the runner's `<street>@<time>-<kind>`; other horizons and modes add a suffix."""
    h = "" if horizon == "nowcast" else f"~{horizon}"
    mode = "~backfill" if is_backfill else "~replay" if is_replay else ""
    return f"{a.street_id}@{a.issued_at:%Y%m%dT%H%M}-{a.kind}{h}{mode}"


def insert_alerts(conn, alerts: list[Alert], *, is_replay: bool, is_backfill: bool,
                  horizon: str = "nowcast") -> list[str]:
    """Insert alerts and return the ids of the NEWLY inserted ones (in order). An id that already exists is left
    untouched and not returned, so callers (push) act only on new alerts after a restart."""
    ids = [_alert_id(a, is_replay, is_backfill, horizon) for a in alerts]
    existing: set[str] = set()
    for part in _chunks(ids):
        existing |= {r[0] for r in conn.execute(select(t.alerts.c.alert_id).where(t.alerts.c.alert_id.in_(part)))}
    rows, seen, new_ids = [], set(existing), []
    for a, aid in zip(alerts, ids):
        if aid in seen:
            continue
        seen.add(aid)
        new_ids.append(aid)
        rows.append({
            "alert_id": aid, "street_id": a.street_id, "township_id": a.street_id.split("-", 1)[0],
            "horizon": horizon, "level": a.level.json, "kind": a.kind, "issued_at": a.issued_at,
            "window_start": a.window_start, "window_end": a.window_end,
            "fired_by_json": json.dumps(list(a.fired_by)), "reasons_json": json.dumps([_reason_dict(r) for r in a.reasons]),
            "inputs_json": None, "recipients": 0, "is_replay": is_replay, "is_backfill": is_backfill,
        })
    if rows:
        conn.execute(insert(t.alerts), rows)
    return new_ids


def replace_backfill(conn, township_id: str, start: datetime, end: datetime) -> int:
    """Delete the township's backfill alerts issued in [start, end) so a re-run rewrites them (idempotent). Returns the count."""
    res = conn.execute(delete(t.alerts).where(t.alerts.c.is_backfill.is_(True), t.alerts.c.township_id == township_id,
                                              t.alerts.c.issued_at >= _naive(start), t.alerts.c.issued_at < _naive(end)))
    return res.rowcount


def outcomes_for(conn, items: list[dict], *, count_simulated_sensor: bool = True, exclude_demo: bool = False) -> dict[str, str]:
    """alert_id -> confirmed | not_confirmed | unverified for dicts with `alert_id`, `street_id`, `kind`, `issued_at`
    (and optionally `is_replay`).

    Answers are scored by stats.outcomes.alert_outcome. The sensor only counts from devices mapped to the alert's
    street (`sensor_devices`):
    - live alerts: REAL readings above the threshold in the 3 h after the alert. Simulated readings never affect a
      live alert (nothing in the AlertSummary would label them).
    - replay alerts (`is_replay`): scored on their demo answers, plus simulated readings of the mapped sensor above the
      threshold with no time window (replay times are 2024); `count_simulated_sensor=False` drops those.

    STATISTICS MUST call list_alerts(include_replay=False, count_simulated_sensor=False, exclude_demo=True);
    `exclude_demo` ignores answers with source='demo'."""
    ids = [i["alert_id"] for i in items]
    by_alert: dict[str, list[dict]] = {}
    for part in _chunks(ids):
        q = select(t.answers).where(t.answers.c.alert_id.in_(part))
        if exclude_demo:
            q = q.where(t.answers.c.source != "demo")
        for r in conn.execute(q):
            by_alert.setdefault(r.alert_id, []).append({
                "device_id": r.device_id, "answer": r.answer, "photo_path": r.photo_path, "distance_m": r.distance_m,
                "answered_at": r.answered_at, "review_status": r.review_status})
    devices = sensor_devices()
    threshold = sensor_threshold_cm()
    live = [i for i in items if i["kind"] == "alert" and not i.get("is_replay")]
    real: list = []
    if live and devices:
        first = min(_naive(i["issued_at"]) for i in live)
        real = list(conn.execute(select(t.sensor_readings).where(
            t.sensor_readings.c.time_local >= first, t.sensor_readings.c.simulated.is_(False),
            t.sensor_readings.c.level_cm > threshold)))
    sim_high: set[str] = set()
    if count_simulated_sensor and any(i.get("is_replay") for i in items) and devices:
        sim_high = {r.device_id for r in conn.execute(select(t.sensor_readings.c.device_id).where(
            t.sensor_readings.c.simulated.is_(True), t.sensor_readings.c.level_cm > threshold).distinct())}
    out = {}
    for i in items:
        if i["kind"] != "alert":
            out[i["alert_id"]] = "unverified"
            continue
        mine = {d for d, streets in devices.items() if i["street_id"] in streets}
        answers = by_alert.get(i["alert_id"], [])
        if i.get("is_replay"):
            # replay alerts carry simulated 2024 times while their demo answers arrive now: no time window
            out[i["alert_id"]] = outcomes.alert_outcome(answers, bool(mine & sim_high))
            continue
        issued = _naive(i["issued_at"])
        hit = outcomes.sensor_above([{"time_local": r.time_local, "level_cm": r.level_cm} for r in real
                                     if r.device_id in mine], issued, threshold)
        out[i["alert_id"]] = outcomes.alert_outcome(answers, hit, issued_at=issued)
    return out


def list_alerts(conn, *, street_id: str | None = None, active: bool = False,
                include_replay: bool = True, since: datetime | None = None, include_backfill: bool = False,
                replay_only: bool = False, count_simulated_sensor: bool = True, alert_id: str | None = None,
                exclude_demo: bool = False, now: datetime | None = None,
                until: datetime | None = None) -> list[dict]:
    """AlertSummary dicts, newest first. Backfill rows are excluded unless `include_backfill`.
    `outcome` is computed from answers and sensor readings (see `outcomes_for`).
    Statistics must pass include_replay=False, count_simulated_sensor=False and exclude_demo=True.

    replay_only: only replay rows (the API's view while a replay is on).
    active: per street, mode (live / replay / backfill) and horizon (nowcast / outlook) the latest row, if it is an 'alert' (not an all-clear)
    AND (the street's current state in that mode is not 'normal' OR that state is less than `alerts.clear_after_min` past
    the alert). The engine holds an all-clear for `clear_after_min`, so a street can be normal while its latest row is still
    an 'alert': that alert stays active during the hold (residents still see it and can confirm it). A missed all-clear,
    e.g. the API was down, drops out of `active` once the hold has passed, so no alert stays active for ever. Streets
    without a saved state row, and backfill rows, are not filtered by state."""
    a = t.alerts
    q = select(a).order_by(a.c.issued_at.desc(), a.c.alert_id)
    if street_id is not None:
        q = q.where(a.c.street_id == street_id)
    if alert_id is not None:
        q = q.where(a.c.alert_id == alert_id)
    if replay_only:
        q = q.where(a.c.is_replay.is_(True))
    elif not include_replay:
        q = q.where(a.c.is_replay.is_(False))
    if not include_backfill:
        q = q.where(a.c.is_backfill.is_(False))
    if since is not None:
        q = q.where(a.c.issued_at >= _naive(since))
    if until is not None:
        q = q.where(a.c.issued_at < _naive(until))
    if active:
        latest = (select(a.c.street_id, a.c.is_replay, a.c.is_backfill, a.c.horizon, func.max(a.c.issued_at).label("m"))
                  .group_by(a.c.street_id, a.c.is_replay, a.c.is_backfill, a.c.horizon).subquery())
        q = (q.join(latest, and_(a.c.street_id == latest.c.street_id, a.c.is_replay == latest.c.is_replay,
                                 a.c.is_backfill == latest.c.is_backfill, a.c.horizon == latest.c.horizon,
                                 a.c.issued_at == latest.c.m))
             .where(a.c.kind == "alert"))
        # the state test (normal now and past the hold) is done in Python on the fetched rows, see _past_the_hold
        # an outlook is active only until its window ends (it has no nowcast state to fall back on)
        q = q.where((a.c.horizon != "outlook") | a.c.window_end.is_(None) | (a.c.window_end > _naive(now or now_myt())))
    pl = push_levels()
    rows = list(conn.execute(q))
    if active:
        rows = _still_active(conn, rows)
    out = outcomes_for(conn, [{"alert_id": r.alert_id, "street_id": r.street_id, "kind": r.kind,
                               "issued_at": r.issued_at, "is_replay": bool(r.is_replay)} for r in rows],
                       count_simulated_sensor=count_simulated_sensor, exclude_demo=exclude_demo)
    capped = _capped_watch_ids(conn, rows, pl)
    return [{
        "alert_id": r.alert_id, "street_id": r.street_id, "horizon": r.horizon, "kind": r.kind, "level": r.level,
        "issued_at": _iso(r.issued_at), "window": _window(r.window_start, r.window_end),
        "outcome": out[r.alert_id],
        "is_replay": bool(r.is_replay), "push": _push(r, pl) and r.alert_id not in capped,
    } for r in rows]


def _still_active(conn, rows):
    """Drop nowcast alert rows whose street is Normal in their mode and whose state is `clear_after_min` or more past the
    alert (the all-clear hold is over, so a missing all-clear must not keep it active). Backfill and outlook rows are kept."""
    ss = t.street_state
    nowcast = [r for r in rows if not r.is_backfill and r.horizon != "outlook"]
    if not nowcast:
        return rows
    normal: dict[tuple, datetime | None] = {}
    for part in _chunks(sorted({r.street_id for r in nowcast})):
        for s in conn.execute(select(ss.c.street_id, ss.c.mode, ss.c.data_time).where(
                ss.c.street_id.in_(part), ss.c.level == "normal")):
            normal[(s.street_id, s.mode)] = s.data_time
    # repo reads the config file (`_alerts_cfg`) while serialize.street_detail uses the runner's `ctx.rules_cfg`; both are
    # config/rules.yaml in production. The runner validates the value once at startup (`engine.alerts.validate_config`).
    hold = alert_clear_after(_alerts_cfg())

    def keep(r) -> bool:
        if r.is_backfill or r.horizon == "outlook":
            return True
        key = (r.street_id, "replay" if r.is_replay else "live")
        if key not in normal:
            return True                  # elevated now, or no saved state
        seen = normal[key]
        return seen is not None and seen - r.issued_at < hold
    return [r for r in rows if keep(r)]


def _capped_watch_ids(conn, rows, pl) -> set[str]:
    """Nowcast Watch alerts that are stored and shown but not pushed: the street already had a pushed Watch in the
    same mode (live / replay) less than `alerts.watch_push_min_gap_h` earlier (owner decision 19 Oct 2026).
    Warning and Danger are never capped. The cap is derived from the stored alerts, so it survives a restart, and
    this is the one place that decides it: the API `push` flag and what the runner sends come from the same value.
    Greedy per street in time order: a Watch pushes when no pushed Watch precedes it within the gap."""
    gap_h = float(_alerts_cfg().get("watch_push_min_gap_h", 0))
    if gap_h <= 0 or "watch" not in pl:
        return set()
    streets = sorted({r.street_id for r in rows if r.kind == "alert" and r.level == "watch"
                      and r.horizon != "outlook" and not r.is_backfill})
    if not streets:
        return set()
    a, gap = t.alerts, timedelta(hours=gap_h)
    history = []
    for part in _chunks(streets):
        history += list(conn.execute(select(a.c.alert_id, a.c.street_id, a.c.is_replay, a.c.issued_at).where(
            a.c.street_id.in_(part), a.c.kind == "alert", a.c.level == "watch", a.c.horizon != "outlook",
            a.c.is_backfill.is_(False)).order_by(a.c.issued_at, a.c.alert_id)))
    last_pushed: dict[tuple, datetime] = {}
    capped: set[str] = set()
    for h in sorted(history, key=lambda h: (h.issued_at, h.alert_id)):
        key = (h.street_id, bool(h.is_replay))
        prev = last_pushed.get(key)
        if prev is not None and h.issued_at - prev < gap:
            capped.add(h.alert_id)
        else:
            last_pushed[key] = h.issued_at
    return capped


def _push(r, pl) -> bool:
    if r.kind != "alert" or r.level not in pl or r.is_backfill:
        return False
    if r.horizon == "outlook":      # only an outlook that is genuinely ahead is pushed (engine.outlook.pushes)
        return outlook_pushes(json.loads(r.reasons_json or "[]"))
    return True


def latest_outlook(conn, township_id: str) -> tuple[Alert | None, list[str]]:
    """The township's most recent live outlook (all rows issued at that moment) and its streets; (None, []) when none.
    The runner reseeds its cooldown / active state from this on startup."""
    a = t.alerts
    base = [a.c.township_id == township_id, a.c.horizon == "outlook", a.c.is_replay.is_(False), a.c.is_backfill.is_(False)]
    last_at = conn.execute(select(func.max(a.c.issued_at)).where(*base)).scalar()
    if last_at is None:
        return None, []
    rows = conn.execute(select(a).where(*base, a.c.issued_at == _naive(last_at)).order_by(a.c.alert_id)).fetchall()
    r0 = rows[0]
    reasons = tuple(Reason(d["code"], d["value"], d["unit"], d.get("station"), d["text"]["en"], d["text"]["ms"])
                    for d in json.loads(r0.reasons_json or "[]"))
    last = Alert(township_id, Level.parse(r0.level), r0.kind, r0.issued_at, r0.window_start, r0.window_end, reasons,
                 tuple(json.loads(r0.fired_by_json or "[]")))
    return last, ([r.street_id for r in rows] if r0.kind == "alert" else [])


# ---------- subscriptions ----------

def upsert_subscription(conn, device_id: str, sub: dict, street_ids: list[str], lang: str) -> None:
    """`sub` is a WebPushSubscription: {endpoint, keys: {p256dh, auth}} (flat p256dh/auth also accepted)."""
    keys = sub.get("keys", sub)
    created = conn.execute(select(t.subscriptions.c.created_at).where(t.subscriptions.c.device_id == device_id)).scalar()
    conn.execute(delete(t.subscriptions).where(t.subscriptions.c.device_id == device_id))
    conn.execute(delete(t.subscription_streets).where(t.subscription_streets.c.device_id == device_id))
    conn.execute(insert(t.subscriptions).values(device_id=device_id, endpoint=sub["endpoint"], p256dh=keys["p256dh"],
                                                auth=keys["auth"], lang=lang, created_at=created or now_myt()))
    if street_ids:
        conn.execute(insert(t.subscription_streets), [{"device_id": device_id, "street_id": s} for s in dict.fromkeys(street_ids)])


def delete_subscription(conn, device_id: str) -> None:
    """Drop only the push subscription and its street links (e.g. the push service said 410 Gone); answers stay."""
    conn.execute(delete(t.subscription_streets).where(t.subscription_streets.c.device_id == device_id))
    conn.execute(delete(t.subscriptions).where(t.subscriptions.c.device_id == device_id))


def delete_device(conn, device_id: str, *, uploads: Path | str | None = None) -> list[Path]:
    """Delete every DB row of the device: subscription, street links, answers.

    Returns the photo files to remove, restricted to those inside the uploads directory (anything else is ignored).
    The caller unlinks them with `remove_files` AFTER its transaction commits."""
    root = Path(uploads or uploads_dir()).resolve()
    photos = [p for (p,) in conn.execute(select(t.answers.c.photo_path).where(
        t.answers.c.device_id == device_id, t.answers.c.photo_path.is_not(None)))]
    conn.execute(delete(t.answers).where(t.answers.c.device_id == device_id))
    conn.execute(delete(t.subscription_streets).where(t.subscription_streets.c.device_id == device_id))
    conn.execute(delete(t.subscriptions).where(t.subscriptions.c.device_id == device_id))
    safe = []
    for p in photos:
        path = (root / p).resolve()     # photo_path is the bare uuid file name (an absolute path also works)
        if path != root and path.is_relative_to(root):
            safe.append(path)
    return safe


def remove_files(paths: list[Path]) -> None:
    """Unlink files returned by `delete_device` (call after commit); missing files are ignored."""
    for p in paths:
        try:
            Path(p).unlink()
        except OSError:
            pass


def list_subscribers(conn, street_id: str) -> list[dict]:
    q = (select(t.subscriptions).join(t.subscription_streets, t.subscription_streets.c.device_id == t.subscriptions.c.device_id)
         .where(t.subscription_streets.c.street_id == street_id).order_by(t.subscriptions.c.device_id))
    return [{"device_id": r.device_id, "endpoint": r.endpoint, "p256dh": r.p256dh, "auth": r.auth, "lang": r.lang}
            for r in conn.execute(q)]


# ---------- answers ----------

def insert_answer(conn, answer: dict) -> str:
    """Store an answer and return its id. Raises DuplicateAnswer on (device_id, alert_id); reports (alert_id None) are free."""
    alert_id = answer.get("alert_id")
    if alert_id is not None and conn.execute(select(t.answers.c.answer_id).where(
            t.answers.c.device_id == answer["device_id"], t.answers.c.alert_id == alert_id)).first():
        raise DuplicateAnswer(f"{answer['device_id']} already answered {alert_id}")
    answer_id = answer.get("answer_id") or uuid.uuid4().hex
    row = {"answer_id": answer_id, "device_id": answer["device_id"], "alert_id": alert_id,
           "street_id": answer["street_id"], "answer": answer["answer"], "depth": answer.get("depth"),
           "photo_path": answer.get("photo_path"), "lat3": answer.get("lat3"), "lon3": answer.get("lon3"),
           "distance_m": answer.get("distance_m"), "answered_at": _naive(answer.get("answered_at")) or now_myt(),
           "review_status": answer.get("review_status", "pending"), "source": answer.get("source", "resident")}
    try:
        with conn.begin_nested():   # SAVEPOINT: a failed insert must not abort the caller's transaction (Postgres)
            conn.execute(insert(t.answers).values(**row))
    except IntegrityError as exc:
        msg = str(exc.orig)
        if "uq_answers_device_alert" in msg or "answers.alert_id" in msg:
            raise DuplicateAnswer(msg) from exc
        raise
    return answer_id


def list_answers(conn, *, alert_id=None, street_id=None, review_status=None) -> list[dict]:
    """Rows as stored. `photo_path` is a server file path; the API layer maps it to the `photo_url` of the Answer type."""
    q = select(t.answers).order_by(t.answers.c.answered_at, t.answers.c.answer_id)
    for col, val in ((t.answers.c.alert_id, alert_id), (t.answers.c.street_id, street_id),
                     (t.answers.c.review_status, review_status)):
        if val is not None:
            q = q.where(col == val)
    return _answer_rows(conn, q)


def _answer_rows(conn, q) -> list[dict]:
    return [{
        "answer_id": r.answer_id, "device_id": r.device_id, "alert_id": r.alert_id, "street_id": r.street_id,
        "answer": r.answer, "depth": r.depth, "photo_path": r.photo_path, "lat3": r.lat3, "lon3": r.lon3,
        "distance_m": r.distance_m, "answered_at": _iso(r.answered_at), "review_status": r.review_status,
        "source": r.source,
    } for r in conn.execute(q)]


def get_answer(conn, answer_id: str) -> dict | None:
    q = select(t.answers).where(t.answers.c.answer_id == answer_id)
    return next(iter(_answer_rows(conn, q)), None)


def set_answer_review(conn, answer_id: str, status: str) -> None:
    conn.execute(update(t.answers).where(t.answers.c.answer_id == answer_id).values(review_status=status))


# ---------- sensor, suggestions, notes ----------

def insert_sensor_reading(conn, device_id: str, time_local: datetime, level_cm: float, simulated: bool) -> None:
    conn.execute(insert(t.sensor_readings).values(device_id=device_id, time_local=_naive(time_local),
                                                  level_cm=level_cm, simulated=simulated))


def upsert_suggestions(conn, suggestions: list[dict]) -> None:
    """Replace by id (evidence stored as JSON). For an existing id, `status`, `note` and `created_at` are kept
    unless the caller passes status/note, so regenerating suggestions does not lose admin decisions."""
    now = now_myt()
    old: dict = {}
    ids = [s["id"] for s in suggestions]
    for part in _chunks(ids):
        for r in conn.execute(select(t.suggestions.c.id, t.suggestions.c.status, t.suggestions.c.note,
                                     t.suggestions.c.created_at).where(t.suggestions.c.id.in_(part))):
            old[r.id] = r
    rows = []
    for s in suggestions:
        o = old.get(s["id"])
        rows.append({
            "id": s["id"], "street_id": s.get("street_id"), "rule": s["rule"], "priority": s["priority"], "text": s["text"],
            "evidence_json": json.dumps(s.get("evidence", {})),
            "status": s["status"] if "status" in s else (o.status if o else "open"),
            "note": s["note"] if "note" in s else (o.note if o else None),
            "period_from": _date(s.get("period_from")), "period_to": _date(s.get("period_to")),
            "created_at": o.created_at if o else now,
        })
    if not rows:
        return
    conn.execute(delete(t.suggestions).where(t.suggestions.c.id == bindparam("b_id")), [{"b_id": r["id"]} for r in rows])
    conn.execute(insert(t.suggestions), rows)


def _date(d: date | str | None) -> date | None:
    return date.fromisoformat(d) if isinstance(d, str) else d


def _suggestion_row(r) -> dict:
    return {"id": r.id, "street_id": r.street_id, "rule": r.rule, "priority": r.priority, "text": r.text,
            "evidence": json.loads(r.evidence_json) if r.evidence_json else {}, "status": r.status, "note": r.note,
            "period_from": r.period_from.isoformat() if r.period_from else None,
            "period_to": r.period_to.isoformat() if r.period_to else None}


def list_suggestions(conn, date_from: date | None = None, date_to: date | None = None) -> list[dict]:
    """Suggestions whose period overlaps [date_from, date_to] (rows without a period always match), best priority first."""
    s = t.suggestions
    q = select(s).order_by(s.c.id)
    if date_from is not None:
        q = q.where(or_(s.c.period_to.is_(None), s.c.period_to >= date_from))
    if date_to is not None:
        q = q.where(or_(s.c.period_from.is_(None), s.c.period_from <= date_to))
    rank = {"high": 0, "medium": 1, "low": 2}
    return sorted((_suggestion_row(r) for r in conn.execute(q)), key=lambda x: rank.get(x["priority"], 3))


def get_suggestion(conn, suggestion_id: str) -> dict | None:
    r = conn.execute(select(t.suggestions).where(t.suggestions.c.id == suggestion_id)).first()
    return _suggestion_row(r) if r else None


def update_suggestion(conn, suggestion_id: str, status: str, note: str | None) -> None:
    conn.execute(update(t.suggestions).where(t.suggestions.c.id == suggestion_id).values(status=status, note=note))


def insert_note(conn, street_id: str, text: str, author: str) -> int:
    res = conn.execute(insert(t.ops_notes).values(street_id=street_id, text=text, author=author, created_at=now_myt()))
    return int(res.inserted_primary_key[0])
