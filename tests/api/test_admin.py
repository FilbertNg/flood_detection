"""Admin endpoints and auth (WP8)."""
import logging
from datetime import date, datetime, timedelta, timezone

import jwt
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from floodready.api import auth
from floodready.api.main import create_app
from floodready.db import repo
from floodready.engine.types import Alert, Level, Reason

API = "/api/v1"
SECRET = "test-secret-that-is-at-least-32-bytes-long"
STREET = "BBR-prone-street"
SUFFIX = "Screening suggestion; site survey needed."


def make_alert(street=STREET, level=Level.WARNING, kind="alert", at=datetime(2024, 11, 12, 9, 0)):
    return Alert(street, level, kind, at, at + timedelta(minutes=30), at + timedelta(minutes=90),
                 (Reason("rain_1h", 60.0, "mm", "1", "Heavy rain", "Hujan lebat"),), ("rule_rain",))


class Admin:
    def __init__(self, client, engine, uploads):
        self.client, self.engine, self.uploads = client, engine, uploads

    def token(self, email="boss@test", password="pw-boss-12345"):
        r = self.client.post(f"{API}/admin/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token']}"}

    def seed_alert(self, **kw):
        with self.engine.begin() as c:
            return repo.insert_alerts(c, [make_alert(**kw)], is_replay=False, is_backfill=True)[0]

    def seed_answer(self, **kw):
        row = {"device_id": "d1", "street_id": STREET, "answer": "yes", "answered_at": datetime(2024, 11, 12, 9, 30), **kw}
        with self.engine.begin() as c:
            return repo.insert_answer(c, row)


@pytest.fixture()
def adm(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("EVENTS_CSV", str(tmp_path / "events.csv"))
    for var in ("ADMIN_EMAIL", "ADMIN_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    (tmp_path / "uploads").mkdir()
    with runner.db.begin() as c:
        auth.create_user(c, "boss@test", "pw-boss-12345", "admin")
        auth.create_user(c, "view@test", "pw-view-12345", "viewer")
    with TestClient(create_app(runner, start_live_loop=False)) as client:
        yield Admin(client, runner.db, tmp_path / "uploads")


PROTECTED = [
    ("GET", "/admin/stats?from=2024-11-01&to=2024-11-30"), ("GET", "/admin/report?month=2024-11"),
    ("GET", "/admin/suggestions"), ("PATCH", "/admin/suggestions/s1"), ("GET", "/admin/answers"),
    ("PATCH", "/admin/answers/a1"), ("POST", "/admin/notes"), ("POST", "/admin/replay"), ("DELETE", "/admin/replay"),
]


# ---------- auth ----------

def test_wrong_password_and_unknown_user_are_401(adm):
    for email, pw in (("boss@test", "nope"), ("ghost@test", "pw-boss-12345"), ("boss@test", "")):
        r = adm.client.post(f"{API}/admin/login", json={"email": email, "password": pw})
        assert r.status_code == 401


def test_login_returns_a_12_hour_hs256_token_with_role(adm):
    r = adm.client.post(f"{API}/admin/login", json={"email": "view@test", "password": "pw-view-12345"})
    assert r.status_code == 200 and set(r.json()) == {"token"}
    claims = jwt.decode(r.json()["token"], SECRET, algorithms=["HS256"])
    assert claims["sub"] == "view@test" and claims["role"] == "viewer"
    assert abs(claims["exp"] - (datetime.now(timezone.utc) + timedelta(hours=12)).timestamp()) < 60


@pytest.mark.parametrize("method,path", PROTECTED)
def test_every_admin_route_needs_a_token(adm, method, path):
    assert adm.client.request(method, f"{API}{path}").status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED)
def test_bad_tokens_are_401(adm, method, path):
    now = datetime.now(timezone.utc)
    tokens = [
        jwt.encode({"sub": "boss@test", "role": "admin", "exp": now - timedelta(minutes=1)}, SECRET, algorithm="HS256"),
        jwt.encode({"sub": "boss@test", "role": "admin", "exp": now + timedelta(hours=1)}, "x" * 40, algorithm="HS256"),
        jwt.encode({"sub": "boss@test", "role": "admin"}, SECRET, algorithm="HS256"),            # no exp
        "not-a-token",
    ]
    for tok in tokens:
        assert adm.client.request(method, f"{API}{path}", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_viewer_reads_but_cannot_write(adm):
    h = adm.token("view@test", "pw-view-12345")
    assert adm.client.get(f"{API}/admin/stats?from=2024-11-01&to=2024-11-30", headers=h).status_code == 200
    assert adm.client.get(f"{API}/admin/answers", headers=h).status_code == 200
    assert adm.client.patch(f"{API}/admin/suggestions/s1", json={"status": "done"}, headers=h).status_code == 403
    assert adm.client.patch(f"{API}/admin/answers/a1", json={"review_status": "valid"}, headers=h).status_code == 403
    assert adm.client.post(f"{API}/admin/notes", json={"street_id": STREET, "text": "x"}, headers=h).status_code == 403
    assert adm.client.post(f"{API}/admin/replay", json={"event": "2024-11-12", "speed": 60}, headers=h).status_code == 403
    assert adm.client.delete(f"{API}/admin/replay", headers=h).status_code == 403


def bearer(adm, claims_role=None, sub="view@test"):
    claims = {"sub": sub, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    if claims_role:
        claims["role"] = claims_role
    return {"Authorization": "Bearer " + jwt.encode(claims, SECRET, algorithm="HS256")}


def test_the_role_comes_from_the_database_not_from_the_token(adm):
    note = {"street_id": STREET, "text": "x"}
    assert adm.client.post(f"{API}/admin/notes", json=note, headers=bearer(adm, "admin")).status_code == 403   # viewer in DB
    assert adm.client.post(f"{API}/admin/notes", json=note, headers=bearer(adm, None, "boss@test")).status_code == 204


def test_a_downgraded_user_loses_write_access_at_once(adm):
    h = adm.token()
    assert adm.client.post(f"{API}/admin/notes", json={"street_id": STREET, "text": "x"}, headers=h).status_code == 204
    with adm.engine.begin() as c:
        auth.create_user(c, "boss@test", "pw-boss-12345", "viewer")
    assert adm.client.post(f"{API}/admin/notes", json={"street_id": STREET, "text": "x"}, headers=h).status_code == 403
    assert adm.client.get(f"{API}/admin/answers", headers=h).status_code == 200


def test_a_deleted_user_is_rejected(adm):
    h = adm.token()
    with adm.engine.begin() as c:
        from sqlalchemy import delete
        from floodready.db import schema
        c.execute(delete(schema.admin_users).where(schema.admin_users.c.email == "boss@test"))
    assert adm.client.get(f"{API}/admin/answers", headers=h).status_code == 401


def test_passwords_are_stored_as_bcrypt_hashes(adm):
    with adm.engine.begin() as c:
        row = auth.get_user(c, "boss@test")
    assert row["password_hash"].startswith("$2") and "pw-boss-12345" not in row["password_hash"]


def test_env_admin_still_works_and_is_admin(runner, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "env@test")
    monkeypatch.setenv("ADMIN_PASSWORD", "env-pass-12345")
    monkeypatch.setenv("JWT_SECRET", SECRET)
    with TestClient(create_app(runner, start_live_loop=False)) as client:
        r = client.post(f"{API}/admin/login", json={"email": "env@test", "password": "env-pass-12345"})
        assert r.status_code == 200
        assert jwt.decode(r.json()["token"], SECRET, algorithms=["HS256"])["role"] == "admin"
        assert client.post(f"{API}/admin/login", json={"email": "env@test", "password": "x"}).status_code == 401


def clean_env(monkeypatch, *keep):
    for var in ("ADMIN_EMAIL", "ADMIN_PASSWORD", "JWT_SECRET", "FLOODREADY_DEV_LOGIN", "UPLOAD_URL_SECRET"):
        if var not in keep:
            monkeypatch.delenv(var, raising=False)


def forged(secret, role="admin"):
    return jwt.encode({"sub": "attacker", "role": role, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, secret,
                      algorithm="HS256")


def test_unconfigured_server_is_closed_even_to_the_published_dev_password_and_secret(runner, monkeypatch):
    clean_env(monkeypatch)
    with TestClient(create_app(runner, start_live_loop=False)) as client:
        body = {"email": auth.DEV_ADMIN[0], "password": auth.DEV_ADMIN[1]}
        r = client.post(f"{API}/admin/login", json=body)
        assert r.status_code == 503 and r.json()["detail"] == "admin login not configured"
        h = {"Authorization": f"Bearer {forged(auth.DEV_SECRET)}"}
        assert client.post(f"{API}/admin/notes", json={"street_id": STREET, "text": "pwned"}, headers=h).status_code == 401
        assert client.get(f"{API}/admin/answers", headers=h).status_code == 401


def test_dev_login_needs_the_explicit_flag_and_warns(runner, monkeypatch, caplog):
    clean_env(monkeypatch)
    monkeypatch.setenv("FLOODREADY_DEV_LOGIN", "1")
    body = {"email": auth.DEV_ADMIN[0], "password": auth.DEV_ADMIN[1]}
    with caplog.at_level(logging.WARNING):
        with TestClient(create_app(runner, start_live_loop=False)) as client:
            r = client.post(f"{API}/admin/login", json=body)
            assert r.status_code == 200
            h = {"Authorization": f"Bearer {r.json()['token']}"}
            assert client.get(f"{API}/admin/answers", headers=h).status_code == 200
    assert any("DEVELOPMENT" in m for m in caplog.messages)


def test_dev_login_is_off_once_an_admin_user_exists_even_with_the_flag(runner, monkeypatch):
    clean_env(monkeypatch)
    monkeypatch.setenv("FLOODREADY_DEV_LOGIN", "1")
    with runner.db.begin() as c:
        auth.create_user(c, "boss@test", "pw-boss-12345", "admin")
    with TestClient(create_app(runner, start_live_loop=False)) as client:
        body = {"email": auth.DEV_ADMIN[0], "password": auth.DEV_ADMIN[1]}
        assert client.post(f"{API}/admin/login", json=body).status_code == 503


def test_dev_login_is_off_when_jwt_secret_is_set_even_with_the_flag(runner, monkeypatch):
    clean_env(monkeypatch)
    monkeypatch.setenv("FLOODREADY_DEV_LOGIN", "1")
    monkeypatch.setenv("JWT_SECRET", SECRET)
    with TestClient(create_app(runner, start_live_loop=False)) as client:
        body = {"email": auth.DEV_ADMIN[0], "password": auth.DEV_ADMIN[1]}
        assert client.post(f"{API}/admin/login", json=body).status_code == 401


def test_a_short_jwt_secret_is_treated_as_unset(runner, monkeypatch):
    clean_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "x")
    with runner.db.begin() as c:
        auth.create_user(c, "boss@test", "pw-boss-12345", "admin")
    with TestClient(create_app(runner, start_live_loop=False)) as client:
        assert client.post(f"{API}/admin/login", json={"email": "boss@test", "password": "pw-boss-12345"}).status_code == 503
        assert client.get(f"{API}/admin/answers", headers={"Authorization": f"Bearer {forged('x')}"}).status_code == 401


def test_api_docs_are_off_unless_dev_mode(runner, monkeypatch):
    clean_env(monkeypatch)
    with TestClient(create_app(runner, start_live_loop=False)) as client:
        assert [client.get(p).status_code for p in ("/docs", "/redoc", "/openapi.json")] == [404, 404, 404]
    monkeypatch.setenv("FLOODREADY_DEV_LOGIN", "1")
    with TestClient(create_app(runner, start_live_loop=False)) as client:
        assert client.get("/openapi.json").status_code == 200


# ---------- brute force and timing ----------

def test_failed_logins_per_email_are_limited_then_429(adm):
    body = {"email": "boss@test", "password": "wrong"}
    codes = [adm.client.post(f"{API}/admin/login", json=body).status_code for _ in range(7)]
    assert codes == [401] * 5 + [429] * 2
    good = adm.client.post(f"{API}/admin/login", json={"email": "boss@test", "password": "pw-boss-12345"})
    assert good.status_code == 429                                  # locked out for the window, even with the right password
    assert adm.client.post(f"{API}/admin/login", json={"email": "view@test", "password": "pw-view-12345"}).status_code == 200


def test_limiter_window_ip_limit_and_success_reset():
    clock = [0.0]
    lim = auth.LoginLimiter(email_limit=2, email_window=100, ip_limit=3, ip_window=10, clock=lambda: clock[0])
    assert lim.allow("ip1", "A@x") and (lim.failed("a@x") or True)
    assert lim.allow("ip1", "a@x") and (lim.failed("a@x") or True)
    clock[0] = 11                                                   # the IP window passed
    assert not lim.allow("ip1", "a@x")                              # but the e-mail has 2 failures
    clock[0] = 101
    assert lim.allow("ip1", "a@x")                                  # e-mail window passed
    lim.failed("a@x"), lim.succeeded("a@x")
    assert lim.failures.get("a@x") is None
    clock[0] = 102
    assert lim.allow("ip2", "b@x") and lim.allow("ip2", "c@x") and lim.allow("ip2", "d@x") and not lim.allow("ip2", "e@x")


def test_unknown_email_costs_a_bcrypt_check_of_the_same_cost_as_a_real_hash():
    rounds = lambda h: h.split("$")[2]                              # noqa: E731  ($2b$12$...)
    assert rounds(auth._DUMMY_HASH.decode()) == rounds(auth.hash_password("x"))


def test_long_passwords_are_rejected_not_truncated(adm):
    with adm.engine.begin() as c, pytest.raises(ValueError):
        auth.create_user(c, "long@test", "x" * 73, "admin")
    assert adm.client.post(f"{API}/admin/login", json={"email": "boss@test", "password": "x" * 500}).status_code == 401


# ---------- stats and report ----------

def test_stats_endpoint_shape_and_validation(adm):
    a = adm.seed_alert()
    adm.seed_answer(alert_id=a)
    adm.seed_answer(alert_id=a, device_id="d2")
    h = adm.token()
    r = adm.client.get(f"{API}/admin/stats", params={"from": "2024-11-01", "to": "2024-11-30"}, headers=h)
    assert r.status_code == 200
    s = r.json()
    assert set(s) == {"period", "kpis", "by_week", "by_street", "rain_at_onset", "station_health", "sources"}
    assert s["kpis"]["alerts"] == 1 and s["kpis"]["confirmed"] == 1 and s["kpis"]["confirmation_rate"] == 1.0
    assert s["by_street"][0]["name"] == "Prone Street"
    assert adm.client.get(f"{API}/admin/stats", params={"from": "2024-11-30", "to": "2024-11-01"}, headers=h).status_code == 422
    assert adm.client.get(f"{API}/admin/stats", params={"from": "x", "to": "2024-11-01"}, headers=h).status_code == 422
    assert adm.client.get(f"{API}/admin/stats", headers=h).status_code == 422


def test_stats_station_health_lists_26558_as_stale_when_blanked(adm, runner):
    day = pd.date_range(datetime(2024, 11, 12), datetime(2024, 11, 12, 23, 45), freq="15min")
    rows = []
    for st in runner.ctx.township["stations"]:
        for kind in (k.lower() for k in st["types"]):
            dead = st["graph_id"] == "26558"
            rows += [(st["graph_id"], kind, t, np.nan if dead else 0.0, np.nan if dead else 1.0) for t in day]
    blank = pd.DataFrame(rows, columns=["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"])
    runner.ctx.load_readings = lambda start, end: blank
    r = adm.client.get(f"{API}/admin/stats", params={"from": "2024-11-12", "to": "2024-11-12"}, headers=adm.token())
    health = {h["graph_id"]: h for h in r.json()["station_health"]}
    assert health["26558"]["stale_pct"] == 1.0
    assert all(h["stale_pct"] == 0.0 for g, h in health.items() if g != "26558") and len(health) == 7
    assert r.json()["station_health"][0]["graph_id"] == "26558"


def test_report_lists_the_12_nov_event(adm, tmp_path):
    (tmp_path / "events.csv").write_text(
        "event_id,street_ids,event_date,start_time_local,date_precision,flooded,place_name,source_type,source_url,"
        "checked_by,status\n"
        f"BBR-2024-11-12-01,{STREET},2024-11-12,2024-11-12 09:00,hour,1,Persiaran Sungai Keramat,news,https://example.org/n,"
        "TESTER,checked\n",
        encoding="utf-8")
    adm.seed_alert()
    r = adm.client.get(f"{API}/admin/report", params={"month": "2024-11"}, headers=adm.token())
    assert r.status_code == 200
    rep = r.json()
    assert set(rep) == {"month", "summary", "events", "top_streets", "suggestions", "data_health"}
    assert [e["event_id"] for e in rep["events"]] == ["BBR-2024-11-12-01"]
    assert rep["events"][0]["date"] == "2024-11-12" and rep["summary"]["confirmed"] == 1     # news confirmed the alert
    assert adm.client.get(f"{API}/admin/report", params={"month": "2024-13"}, headers=adm.token()).status_code == 422


# ---------- suggestions ----------

def seed_suggestion(adm, sid="s1", text="Drainage capacity review."):
    with adm.engine.begin() as c:
        repo.upsert_suggestions(c, [{"id": sid, "street_id": STREET, "rule": "SUG-1", "priority": "high", "text": text,
                                     "evidence": {"rain_at_onset_mm": [35, 42, 48]},
                                     "period_from": date(2024, 1, 1), "period_to": date(2024, 12, 31)}])


def test_suggestions_list_and_update(adm):
    seed_suggestion(adm)
    h = adm.token()
    [s] = adm.client.get(f"{API}/admin/suggestions", params={"from": "2024-11-01", "to": "2024-11-30"}, headers=h).json()
    assert s == {"id": "s1", "street_id": STREET, "street_name": "Prone Street", "rule": "SUG-1", "priority": "high",
                 "text": f"Drainage capacity review. {SUFFIX}", "evidence": {"rain_at_onset_mm": [35, 42, 48]},
                 "status": "open", "note": None}
    assert adm.client.get(f"{API}/admin/suggestions", params={"from": "2026-01-01", "to": "2026-02-01"}, headers=h).json() == []
    r = adm.client.patch(f"{API}/admin/suggestions/s1", json={"status": "accepted", "note": "Survey booked"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "accepted" and r.json()["note"] == "Survey booked"
    assert adm.client.get(f"{API}/admin/suggestions", headers=h).json()[0]["status"] == "accepted"


def test_suggestion_text_with_the_suffix_is_not_doubled(adm):
    seed_suggestion(adm, text=f"Check it. {SUFFIX}")
    [s] = adm.client.get(f"{API}/admin/suggestions", headers=adm.token()).json()
    assert s["text"] == f"Check it. {SUFFIX}"


def test_suggestion_update_validation(adm):
    seed_suggestion(adm)
    h = adm.token()
    assert adm.client.patch(f"{API}/admin/suggestions/s1", json={"status": "bogus"}, headers=h).status_code == 422
    assert adm.client.patch(f"{API}/admin/suggestions/s1", json={}, headers=h).status_code == 422
    assert adm.client.patch(f"{API}/admin/suggestions/missing", json={"status": "done"}, headers=h).status_code == 404
    assert adm.client.patch(f"{API}/admin/suggestions/s1", json={"status": "done", "note": "x" * 2001}, headers=h).status_code == 422


# ---------- answers ----------

def test_answers_filter_review_and_photo_url(adm):
    a = adm.seed_alert()
    pending = adm.seed_answer(alert_id=a, photo_path="abc123.jpg")
    adm.seed_answer(device_id="d2", alert_id=a, review_status="valid")
    h = adm.token()
    rows = adm.client.get(f"{API}/admin/answers", params={"review_status": "pending"}, headers=h).json()
    assert [r["answer_id"] for r in rows] == [pending]
    assert rows[0]["photo_url"].startswith("/uploads/abc123.jpg?exp=") and "&sig=" in rows[0]["photo_url"]
    assert "photo_path" not in rows[0]
    assert set(rows[0]) == {"answer_id", "device_id", "alert_id", "street_id", "answer", "depth", "photo_url", "lat3", "lon3",
                            "distance_m", "answered_at", "review_status", "source"}
    assert len(adm.client.get(f"{API}/admin/answers", headers=h).json()) == 2
    assert adm.client.get(f"{API}/admin/answers", params={"review_status": "bogus"}, headers=h).status_code == 422
    r = adm.client.patch(f"{API}/admin/answers/{pending}", json={"review_status": "spam"}, headers=h)
    assert r.status_code == 200 and r.json()["review_status"] == "spam"
    assert adm.client.get(f"{API}/admin/answers", params={"review_status": "pending"}, headers=h).json() == []


def test_answer_review_validation(adm):
    aid = adm.seed_answer()
    h = adm.token()
    for body in ({"review_status": "pending"}, {"review_status": "bogus"}, {}):
        assert adm.client.patch(f"{API}/admin/answers/{aid}", json=body, headers=h).status_code == 422
    assert adm.client.patch(f"{API}/admin/answers/nope", json={"review_status": "valid"}, headers=h).status_code == 404


def test_demo_answers_are_listed_for_review_but_labelled(adm):
    adm.seed_answer(source="demo")
    [row] = adm.client.get(f"{API}/admin/answers", headers=adm.token()).json()
    assert row["source"] == "demo"


# ---------- notes ----------

def test_note_stores_author_from_the_token(adm):
    r = adm.client.post(f"{API}/admin/notes", json={"street_id": STREET, "text": "drain cleared"}, headers=adm.token())
    assert r.status_code == 204 and r.content == b""
    with adm.engine.begin() as c:
        from sqlalchemy import select
        from floodready.db import schema
        [row] = c.execute(select(schema.ops_notes)).all()
    assert (row.street_id, row.text, row.author) == (STREET, "drain cleared", "boss@test")


def test_note_validation(adm):
    h = adm.token()
    assert adm.client.post(f"{API}/admin/notes", json={"street_id": "BBR-nope", "text": "x"}, headers=h).status_code == 404
    assert adm.client.post(f"{API}/admin/notes", json={"street_id": STREET, "text": ""}, headers=h).status_code == 422
    assert adm.client.post(f"{API}/admin/notes", json={"street_id": STREET, "text": "x" * 2001}, headers=h).status_code == 422
    assert adm.client.post(f"{API}/admin/notes", json={"text": "x"}, headers=h).status_code == 422


# ---------- uploads ----------

def signed(name, ttl=3600, key=SECRET, now=None):
    return auth.sign_upload(name, key, now=now, ttl=ttl)


def test_uploads_are_served_read_only_with_a_valid_signature(adm):
    (adm.uploads / "abc123.jpg").write_bytes(b"\xff\xd8jpegdata")
    r = adm.client.get(signed("abc123.jpg"))
    assert r.status_code == 200 and r.content == b"\xff\xd8jpegdata"
    assert r.headers["content-type"] == "image/jpeg" and r.headers["x-content-type-options"] == "nosniff"
    assert adm.client.get(signed("missing.jpg")).status_code == 404
    assert adm.client.put(signed("abc123.jpg"), content=b"x").status_code == 405
    assert adm.client.delete(signed("abc123.jpg")).status_code == 405


def test_the_review_queue_link_works_and_a_bad_or_expired_signature_does_not(adm):
    (adm.uploads / "abc123.jpg").write_bytes(b"jpegdata")
    adm.seed_answer(photo_path="abc123.jpg")
    [row] = adm.client.get(f"{API}/admin/answers", headers=adm.token()).json()
    assert adm.client.get(row["photo_url"]).status_code == 200
    assert adm.client.get("/uploads/abc123.jpg").status_code == 404                          # no signature
    assert adm.client.get("/uploads/abc123.jpg?exp=9999999999&sig=" + "0" * 32).status_code == 404   # bad signature
    assert adm.client.get(signed("abc123.jpg", ttl=-10)).status_code == 404                  # expired
    assert adm.client.get(signed("abc123.jpg", key="k" * 40)).status_code == 404            # wrong key
    other = signed("other.jpg").replace("other.jpg", "abc123.jpg")                          # signature of another file
    assert adm.client.get(other).status_code == 404


@pytest.mark.parametrize("name", ["..%2Fsecret.txt", "..%5Csecret.txt", "%2e%2e%2fsecret.txt", "a.txt", ".hidden.jpg",
                                  "abc.jpg%00.png", "sub%2Fabc.jpg", "C%3A%5Cwindows%5Cwin.ini", "abc"])
def test_upload_paths_are_confined_even_with_a_valid_signature(adm, name):
    (adm.uploads.parent / "secret.txt").write_text("secret")
    (adm.uploads / "a.txt").write_text("not an image")
    for raw in (name, name.replace("%2F", "/").replace("%5C", "\\")):
        exp = int(__import__("time").time()) + 600
        sig = auth._upload_sig(raw, exp, SECRET)
        r = adm.client.get(f"/uploads/{name}?exp={exp}&sig={sig}")
        assert r.status_code == 404 and b"secret" not in r.content and b"not an image" not in r.content


def test_non_ascii_signature_is_a_404_not_a_500(adm):
    (adm.uploads / "abc123.jpg").write_bytes(b"x")
    exp = int(__import__("time").time()) + 600
    assert adm.client.get(f"/uploads/abc123.jpg?exp={exp}&sig=%C3%A9%C3%A9").status_code == 404
    assert adm.client.get(f"/uploads/abc123.jpg?exp=%D9%A1%D9%A2&sig=abc").status_code == 404


def test_stats_and_report_survive_an_area_row_next_to_a_street_row(adm, tmp_path):
    (tmp_path / "events.csv").write_text(
        "event_id,street_ids,event_date,start_time_local,date_precision,flooded,sdp_township,place_name,source_type,"
        "source_url,checked_by,status\n"
        "area,,2024-11-12,,day,1,Bandar Bukit Raja,Area,news,https://example.org/a,TESTER,checked\n"
        f"st,{STREET},2024-11-20,2024-11-20 09:30,hour,1,,Street,news,https://example.org/b,TESTER,checked\n",
        encoding="utf-8")
    h = adm.token()
    assert adm.client.get(f"{API}/admin/stats", params={"from": "2024-11-01", "to": "2024-11-30"}, headers=h).status_code == 200
    r = adm.client.get(f"{API}/admin/report", params={"month": "2024-11"}, headers=h)
    assert r.status_code == 200 and [e["event_id"] for e in r.json()["events"]] == ["area", "st"]


# ---------- result cache (stats and report) ----------

def stats_nov(adm, h):
    return adm.client.get(f"{API}/admin/stats", params={"from": "2024-11-01", "to": "2024-11-30"}, headers=h).json()


def test_stats_are_cached_until_a_write_that_feeds_them(adm):
    a = adm.seed_alert()
    adm.seed_answer(alert_id=a)
    second = adm.seed_answer(alert_id=a, device_id="d2")
    h = adm.token()
    assert stats_nov(adm, h)["kpis"]["confirmed"] == 1
    adm.seed_alert(at=datetime(2024, 11, 20, 9, 0))         # written behind the API's back: the cached result stands
    assert stats_nov(adm, h)["kpis"]["alerts"] == 1
    r = adm.client.patch(f"{API}/admin/answers/{second}", json={"review_status": "spam"}, headers=h)
    assert r.status_code == 200
    s = stats_nov(adm, h)                                  # the review cleared the cache
    assert s["kpis"]["alerts"] == 2 and s["kpis"]["confirmed"] == 0


def test_a_rejected_write_or_a_login_does_not_clear_the_cache(adm):
    adm.seed_alert()
    h = adm.token()
    stats_nov(adm, h)
    adm.seed_alert(at=datetime(2024, 11, 20, 9, 0))
    viewer = adm.token("view@test", "pw-view-12345")
    assert adm.client.post(f"{API}/admin/notes", json={"street_id": STREET, "text": "x"}, headers=viewer).status_code == 403
    adm.client.post(f"{API}/admin/preview")
    assert stats_nov(adm, h)["kpis"]["alerts"] == 1


def test_warm_precomputes_the_default_statistics_and_this_months_report(adm, monkeypatch):
    from floodready.stats import report as report_mod
    from floodready.stats import statistics
    adm.seed_alert()
    adm.client.app.state.warm_admin(datetime(2024, 11, 30, 10, 0))
    monkeypatch.setattr(statistics, "stats", lambda *a, **k: pytest.fail("stats recomputed"))
    monkeypatch.setattr(report_mod, "monthly_report", lambda *a, **k: pytest.fail("report recomputed"))
    h = adm.token()
    r = adm.client.get(f"{API}/admin/stats", params={"from": "2024-01-01", "to": "2024-11-30"}, headers=h)
    assert r.status_code == 200 and r.json()["kpis"]["alerts"] == 1
    assert adm.client.get(f"{API}/admin/report", params={"month": "2024-11"}, headers=h).status_code == 200
