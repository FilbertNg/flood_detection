"""Repository over the database tables (build plan §4.3; WP1 interface §3.1).

SQLAlchemy 2 Core only. Callers pass a Connection (e.g. `with engine.begin() as conn`) and own the transaction.
Datetimes are stored naive MYT and returned as ISO 8601 with +08:00.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Engine, and_, bindparam, create_engine, delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from ..engine.types import Alert, StreetState
from ..jobs import now_myt
from . import schema as t

COOLDOWN_MIN = 60                                   # config/rules.yaml alerts.cooldown_min
PUSH_LEVELS = ("watch", "warning", "danger")        # config/rules.yaml alerts.push_levels
_CHUNK = 400


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


def get_street_states(conn, township_id: str, mode: str) -> list[dict]:
    """States of one township; street ids are `<TOWNSHIP>-<slug>`, so the prefix selects the township."""
    q = select(t.street_state).where(t.street_state.c.mode == mode,
                                     t.street_state.c.street_id.like(f"{township_id}-%")).order_by(t.street_state.c.street_id)
    return [{
        "street_id": r.street_id, "mode": r.mode, "level": r.level, "trigger_level": r.trigger_level,
        "confidence": r.confidence, "flood_probability": r.flood_probability,
        "fired_by": json.loads(r.fired_by_json or "[]"), "window": _window(r.window_start, r.window_end),
        "reasons": json.loads(r.reasons_json or "[]"), "data_time": _iso(r.data_time), "updated_at": _iso(r.updated_at),
    } for r in conn.execute(q)]


# ---------- alerts ----------

def _alert_id(a: Alert, is_replay: bool, is_backfill: bool) -> str:
    suffix = "~backfill" if is_backfill else "~replay" if is_replay else ""
    return f"{a.street_id}@{a.issued_at:%Y%m%dT%H%M}-{a.kind}{suffix}"


def insert_alerts(conn, alerts: list[Alert], *, is_replay: bool, is_backfill: bool) -> list[str]:
    """Insert alerts, returning their ids in order. An id that already exists is left untouched (idempotent)."""
    ids = [_alert_id(a, is_replay, is_backfill) for a in alerts]
    existing: set[str] = set()
    for part in _chunks(ids):
        existing |= {r[0] for r in conn.execute(select(t.alerts.c.alert_id).where(t.alerts.c.alert_id.in_(part)))}
    rows, seen = [], set(existing)
    for a, aid in zip(alerts, ids):
        if aid in seen:
            continue
        seen.add(aid)
        rows.append({
            "alert_id": aid, "street_id": a.street_id, "township_id": a.street_id.split("-", 1)[0],
            "horizon": "nowcast", "level": a.level.json, "kind": a.kind, "issued_at": a.issued_at,
            "window_start": a.window_start, "window_end": a.window_end,
            "fired_by_json": json.dumps(list(a.fired_by)), "reasons_json": json.dumps([_reason_dict(r) for r in a.reasons]),
            "inputs_json": None, "recipients": 0, "is_replay": is_replay, "is_backfill": is_backfill,
        })
    if rows:
        conn.execute(insert(t.alerts), rows)
    return ids


def list_alerts(conn, *, street_id: str | None = None, active: bool = False,
                include_replay: bool = True, since: datetime | None = None) -> list[dict]:
    """AlertSummary dicts, newest first. `outcome` is 'unverified' here; WP4 fills it from answers and sensors.

    active: per street, the latest alert if it is an 'alert' (not an all-clear) still inside its window or cooldown."""
    q = select(t.alerts).order_by(t.alerts.c.issued_at.desc(), t.alerts.c.alert_id)
    if street_id is not None:
        q = q.where(t.alerts.c.street_id == street_id)
    if not include_replay:
        q = q.where(t.alerts.c.is_replay.is_(False))
    if since is not None:
        q = q.where(t.alerts.c.issued_at >= _naive(since))
    rows = list(conn.execute(q))
    if active:
        now, latest = now_myt(), {}
        for r in rows:                                   # newest first: first seen per street is the latest
            latest.setdefault(r.street_id, r)
        rows = [r for r in rows if latest[r.street_id] is r and r.kind == "alert" and
                ((r.window_end is not None and r.window_end >= now) or r.issued_at + timedelta(minutes=COOLDOWN_MIN) >= now)]
    return [{
        "alert_id": r.alert_id, "street_id": r.street_id, "horizon": r.horizon, "kind": r.kind, "level": r.level,
        "issued_at": _iso(r.issued_at), "window": _window(r.window_start, r.window_end), "outcome": "unverified",
        "is_replay": bool(r.is_replay), "push": r.kind == "alert" and r.level in PUSH_LEVELS,
    } for r in rows]


# ---------- subscriptions ----------

def upsert_subscription(conn, device_id: str, sub: dict, street_ids: list[str], lang: str) -> None:
    """`sub` is a WebPushSubscription: {endpoint, keys: {p256dh, auth}} (flat p256dh/auth also accepted)."""
    keys = sub.get("keys", sub)
    conn.execute(delete(t.subscriptions).where(t.subscriptions.c.device_id == device_id))
    conn.execute(delete(t.subscription_streets).where(t.subscription_streets.c.device_id == device_id))
    conn.execute(insert(t.subscriptions).values(device_id=device_id, endpoint=sub["endpoint"], p256dh=keys["p256dh"],
                                                auth=keys["auth"], lang=lang, created_at=now_myt()))
    if street_ids:
        conn.execute(insert(t.subscription_streets), [{"device_id": device_id, "street_id": s} for s in dict.fromkeys(street_ids)])


def delete_device(conn, device_id: str) -> None:
    """Delete every row of the device: subscription, street links, answers and their photo files."""
    photos = [p for (p,) in conn.execute(select(t.answers.c.photo_path).where(
        t.answers.c.device_id == device_id, t.answers.c.photo_path.is_not(None)))]
    conn.execute(delete(t.answers).where(t.answers.c.device_id == device_id))
    conn.execute(delete(t.subscription_streets).where(t.subscription_streets.c.device_id == device_id))
    conn.execute(delete(t.subscriptions).where(t.subscriptions.c.device_id == device_id))
    for p in photos:
        try:
            os.remove(p)
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
        conn.execute(insert(t.answers).values(**row))
    except IntegrityError as exc:
        raise DuplicateAnswer(str(exc.orig)) from exc
    return answer_id


def list_answers(conn, *, alert_id=None, street_id=None, review_status=None) -> list[dict]:
    q = select(t.answers).order_by(t.answers.c.answered_at, t.answers.c.answer_id)
    for col, val in ((t.answers.c.alert_id, alert_id), (t.answers.c.street_id, street_id),
                     (t.answers.c.review_status, review_status)):
        if val is not None:
            q = q.where(col == val)
    return [{
        "answer_id": r.answer_id, "device_id": r.device_id, "alert_id": r.alert_id, "street_id": r.street_id,
        "answer": r.answer, "depth": r.depth, "photo_path": r.photo_path, "lat3": r.lat3, "lon3": r.lon3,
        "distance_m": r.distance_m, "answered_at": _iso(r.answered_at), "review_status": r.review_status,
        "source": r.source,
    } for r in conn.execute(q)]


def set_answer_review(conn, answer_id: str, status: str) -> None:
    conn.execute(update(t.answers).where(t.answers.c.answer_id == answer_id).values(review_status=status))


# ---------- sensor, suggestions, notes ----------

def insert_sensor_reading(conn, device_id: str, time_local: datetime, level_cm: float, simulated: bool) -> None:
    conn.execute(insert(t.sensor_readings).values(device_id=device_id, time_local=_naive(time_local),
                                                  level_cm=level_cm, simulated=simulated))


def upsert_suggestions(conn, suggestions: list[dict]) -> None:
    """Replace by id. `evidence` (dict) is stored as JSON; `period_from/to` are dates or ISO dates."""
    now = now_myt()
    rows = []
    for s in suggestions:
        rows.append({
            "id": s["id"], "street_id": s.get("street_id"), "rule": s["rule"], "priority": s["priority"], "text": s["text"],
            "evidence_json": json.dumps(s.get("evidence", {})), "status": s.get("status", "open"), "note": s.get("note"),
            "period_from": _date(s.get("period_from")), "period_to": _date(s.get("period_to")), "created_at": now,
        })
    if not rows:
        return
    conn.execute(delete(t.suggestions).where(t.suggestions.c.id == bindparam("b_id")), [{"b_id": r["id"]} for r in rows])
    conn.execute(insert(t.suggestions), rows)


def _date(d: date | str | None) -> date | None:
    return date.fromisoformat(d) if isinstance(d, str) else d


def update_suggestion(conn, suggestion_id: str, status: str, note: str | None) -> None:
    conn.execute(update(t.suggestions).where(t.suggestions.c.id == suggestion_id).values(status=status, note=note))


def insert_note(conn, street_id: str, text: str, author: str) -> int:
    res = conn.execute(insert(t.ops_notes).values(street_id=street_id, text=text, author=author, created_at=now_myt()))
    return int(res.inserted_primary_key[0])
