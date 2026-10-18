import importlib.util
import io
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from floodready.api.main import create_app
from floodready.db import repo
from floodready.engine.types import Alert, Level, Reason
from floodready.jobs import now_myt

API = "/api/v1"
STREET = "BBR-prone-street"
ROOT = Path(__file__).resolve().parents[2]


def make_alert(street=STREET, level=Level.WARNING, kind="alert", at=None):
    at = at or now_myt().replace(second=0, microsecond=0)
    return Alert(street, level, kind, at, at + timedelta(minutes=30), at + timedelta(minutes=90),
                 (Reason("rain_1h", 60.0, "mm", "1", "Heavy rain", "Hujan lebat"),), ("rule_rain",))


class Api:
    def __init__(self, client, engine, uploads, calls):
        self.client, self.engine, self.uploads, self.calls = client, engine, uploads, calls

    def alert(self, **kw):
        replay = kw.pop("is_replay", False)
        with self.engine.begin() as c:
            return repo.insert_alerts(c, [make_alert(**kw)], is_replay=replay, is_backfill=False)[0]

    def post(self, device="d1", answer="yes", street=STREET, alert_id=None, files=None, **extra):
        data = {"device_id": device, "street_id": street, "answer": answer, **extra}
        if alert_id:
            data["alert_id"] = alert_id
        return self.client.post(f"{API}/answers", data=data, files=files)

    def subscribe(self, *devices, street=STREET):
        with self.engine.begin() as c:
            for d in devices:
                repo.upsert_subscription(c, d, {"endpoint": f"https://push.example/{d}", "keys": {"p256dh": "k", "auth": "a"}},
                                         [street], "en")

    def rows(self, **kw):
        with self.engine.begin() as c:
            return repo.list_answers(c, **kw)


@pytest.fixture()
def api(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("SENSOR_TOKEN", "sensor-secret")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@test")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("JWT_SECRET", "test-secret-that-is-at-least-32-bytes-long")
    monkeypatch.setattr(repo, "sensor_devices",
                        lambda: {"sensor-1": {STREET}, "sensor-2": {STREET}, "sim-1": {STREET}, "far-1": {"BBR-safe-street"}})
    engine = repo.connect("sqlite://")
    calls = []
    app = create_app(runner, start_live_loop=False, engine=engine, on_alert_confirmed=calls.append)
    with TestClient(app) as client:
        yield Api(client, engine, tmp_path / "uploads", calls)


def jpeg(size=(40, 30), exif=True, fmt="JPEG", mode="RGB") -> bytes:
    img = Image.new(mode, size, (200, 30, 30))
    buf = io.BytesIO()
    if exif:
        ex = Image.Exif()
        ex[0x010F] = "SecretCam"            # Make
        ex[0x0132] = "2024:11:12 09:00:00"   # DateTime
        gps = ex.get_ifd(0x8825)
        gps[1], gps[2], gps[3], gps[4] = "N", (3.0, 5.0, 12.0), "E", (101.0, 26.0, 15.0)
        img.save(buf, fmt, exif=ex)
    else:
        img.save(buf, fmt)
    return buf.getvalue()


# ---------- validation ----------

def test_answer_is_created(api):
    aid = api.alert()
    r = api.post(alert_id=aid, depth="knee")
    assert r.status_code == 200 and set(r.json()) == {"answer_id"}
    [row] = api.rows()
    assert row["answer_id"] == r.json()["answer_id"] and row["alert_id"] == aid and row["depth"] == "knee"
    assert row["source"] == "resident" and row["review_status"] == "pending"


def test_unknown_street_is_404(api):
    assert api.post(street="BBR-nowhere").status_code == 404


@pytest.mark.parametrize("extra", [{"answer": "maybe"}, {"depth": "ocean"}, {"lat": "95", "lon": "101"}, {"lat": "3.1"},
                                   {"device_id": ""}, {"device_id": "x" * 65}])
def test_bad_fields_are_422(api, extra):
    assert api.post(**extra).status_code == 422


def test_alert_must_exist_and_belong_to_the_street(api):
    other = api.alert(street="BBR-safe-street")
    assert api.post(alert_id=other).status_code == 422
    assert api.post(alert_id="nope@20240101T0000-alert").status_code == 422
    assert api.rows() == []


def test_second_answer_for_the_same_alert_is_409(api):
    aid = api.alert()
    assert api.post(alert_id=aid).status_code == 200
    assert api.post(alert_id=aid, answer="no").status_code == 409
    assert api.post(device="d2", alert_id=aid).status_code == 200
    assert len(api.rows()) == 2


def test_reports_without_an_alert_are_not_limited(api):
    assert api.post(answer="report").status_code == 200
    assert api.post(answer="report").status_code == 200
    assert [r["alert_id"] for r in api.rows()] == [None, None]


# ---------- location ----------

def test_location_is_rounded_to_three_decimals_and_distance_computed(api):
    r = api.post(answer="report", lat="3.08951234", lon="101.42551999")
    assert r.status_code == 200
    [row] = api.rows()
    assert (row["lat3"], row["lon3"]) == (3.09, 101.426)
    assert 0 <= row["distance_m"] < 300          # the fixture street is at about 3.0895, 101.4255


def test_far_answer_has_a_distance_over_one_km(api):
    api.post(answer="report", lat="3.2", lon="101.5")
    [row] = api.rows()
    assert row["distance_m"] > 1000


def test_no_location_means_no_distance(api):
    api.post(answer="report")
    [row] = api.rows()
    assert row["lat3"] is None and row["distance_m"] is None


# ---------- photo ----------

def test_photo_is_reencoded_without_exif_and_stored_under_a_random_name(api):
    src = jpeg()
    assert Image.open(io.BytesIO(src)).getexif()             # the fixture really has EXIF
    r = api.post(answer="report", files={"photo": ("my-house-Jalan-Makyong.jpg", src, "image/jpeg")})
    assert r.status_code == 200
    [row] = api.rows()
    assert row["photo_path"] == Path(row["photo_path"]).name       # only the file name, never a server path
    path = api.uploads / row["photo_path"]
    assert "Makyong" not in path.name and path.suffix == ".jpg" and path.exists()
    with Image.open(path) as img:
        assert len(img.getexif()) == 0 and "exif" not in img.info and img.size == (40, 30)
    assert b"SecretCam" not in path.read_bytes() and b"Exif" not in path.read_bytes()


def test_png_with_alpha_is_accepted(api):
    r = api.post(answer="report", files={"photo": ("a.png", jpeg(exif=False, fmt="PNG", mode="RGBA"), "image/png")})
    assert r.status_code == 200
    with Image.open(api.uploads / api.rows()[0]["photo_path"]) as img:
        assert img.format == "JPEG"


def test_photo_over_10_mb_is_rejected_and_nothing_is_stored(api):
    big = b"\xff\xd8" + b"0" * (10 * 1024 * 1024 + 1)
    r = api.post(answer="report", files={"photo": ("big.jpg", big, "image/jpeg")})
    assert r.status_code == 413 and api.rows() == []


@pytest.mark.parametrize("name,content,ctype", [("a.txt", b"hello", "text/plain"), ("a.jpg", b"not an image", "image/jpeg")])
def test_non_images_are_rejected(api, name, content, ctype):
    r = api.post(answer="report", files={"photo": (name, content, ctype)})
    assert r.status_code == 422 and api.rows() == []
    assert not api.uploads.exists() or list(api.uploads.iterdir()) == []


def test_duplicate_answer_leaves_no_orphan_photo(api):
    aid = api.alert()
    api.post(alert_id=aid, files={"photo": ("a.jpg", jpeg(), "image/jpeg")})
    r = api.post(alert_id=aid, files={"photo": ("b.jpg", jpeg(), "image/jpeg")})
    assert r.status_code == 409 and len(list(api.uploads.iterdir())) == 1


# ---------- replay / demo ----------

def test_answers_to_replay_alerts_are_flagged_demo(api):
    aid = api.alert(is_replay=True)
    api.post(alert_id=aid)
    assert api.rows()[0]["source"] == "demo"


def test_replay_snapshot_alerts_are_found_and_demo(api):
    token = api.client.post(f"{API}/admin/login", json={"email": "admin@test", "password": "secret"}).json()["token"]
    r = api.client.post(f"{API}/admin/replay", json={"event": "2024-11-12", "speed": 0, "stop_at": "09:00"},
                        headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    alert = next(a for a in api.client.get(f"{API}/alerts").json() if a["street_id"] == STREET and a["kind"] == "alert")
    assert alert["outcome"] == "unverified"
    assert api.post(device="a", alert_id=alert["alert_id"]).status_code == 200
    assert api.post(device="b", alert_id=alert["alert_id"]).status_code == 200
    assert {r["source"] for r in api.rows()} == {"demo"}
    alerts = api.client.get(f"{API}/alerts").json()
    assert next(a for a in alerts if a["alert_id"] == alert["alert_id"])["outcome"] == "confirmed"
    detail = api.client.get(f"{API}/streets/{STREET}").json()
    assert next(a for a in detail["history"] if a["alert_id"] == alert["alert_id"])["outcome"] == "confirmed"


# ---------- confirmation push hook ----------

def test_hook_fires_once_when_the_alert_becomes_confirmed(api):
    api.subscribe("a", "b", "c")
    aid = api.alert()
    api.post(device="a", alert_id=aid)
    assert api.calls == []
    api.post(device="b", alert_id=aid)
    assert [c["alert_id"] for c in api.calls] == [aid] and api.calls[0]["outcome"] == "confirmed"
    api.post(device="c", alert_id=aid)
    api.post(device="d", answer="no", alert_id=aid)
    assert len(api.calls) == 1


def test_hook_needs_a_confirming_device_subscribed_to_the_street(api):
    api.subscribe("a", street="BBR-safe-street")             # subscribed, but to another street
    aid = api.alert()
    api.post(device="a", alert_id=aid)
    api.post(device="b", alert_id=aid)
    assert api.calls == []
    with api.engine.begin() as c:
        assert repo.list_alerts(c)[0]["outcome"] == "confirmed"      # still confirmed, only the push is withheld


def test_one_yes_with_photo_confirms(api):
    api.subscribe("d1")
    aid = api.alert()
    api.post(device="d1", alert_id=aid, files={"photo": ("a.jpg", jpeg(), "image/jpeg")})
    assert len(api.calls) == 1


def test_no_answers_never_trigger_the_hook(api):
    aid = api.alert()
    for i in range(4):
        api.post(device=f"n{i}", answer="no", alert_id=aid)
    assert api.calls == []


def test_failed_hook_does_not_fail_the_request(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    engine = repo.connect("sqlite://")

    def boom(_alert):
        raise RuntimeError("push down")
    with TestClient(create_app(runner, start_live_loop=False, engine=engine, on_alert_confirmed=boom)) as client:
        with engine.begin() as c:
            aid = repo.insert_alerts(c, [make_alert()], is_replay=False, is_backfill=False)[0]
            for d in ("a", "b"):
                repo.upsert_subscription(c, d, {"endpoint": "https://p/" + d, "keys": {"p256dh": "k", "auth": "a"}}, [STREET], "en")
        for d in ("a", "b"):
            assert client.post(f"{API}/answers", data={"device_id": d, "street_id": STREET, "answer": "yes", "alert_id": aid}).status_code == 200


# ---------- sensor ----------

def reading(level=40.0, simulated=False, device="sensor-1"):
    return {"device_id": device, "level_cm": level, "simulated": simulated}


def test_sensor_requires_the_token(api):
    url = f"{API}/sensor/readings"
    assert api.client.post(url, json=reading()).status_code == 401
    assert api.client.post(url, json=reading(), headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert api.client.post(url, json=reading(), headers={"Authorization": "sensor-secret"}).status_code == 401


def test_sensor_is_closed_when_no_token_is_configured(api, monkeypatch):
    monkeypatch.delenv("SENSOR_TOKEN")
    assert api.client.post(f"{API}/sensor/readings", json=reading(), headers={"Authorization": "Bearer "}).status_code == 401


H = {"Authorization": "Bearer sensor-secret"}


def stored_sensor_rows(api):
    from sqlalchemy import select
    from floodready.db import schema
    with api.engine.begin() as c:
        return c.execute(select(schema.sensor_readings)).all()


def test_sensor_reading_is_stored_with_its_simulated_flag(api):
    assert api.client.post(f"{API}/sensor/readings", json=reading(5.0, True, "sim-1"), headers=H).status_code == 204
    [row] = stored_sensor_rows(api)
    assert (row.device_id, row.level_cm, row.simulated) == ("sim-1", 5.0, True)


def test_unknown_sensor_device_is_422(api):
    r = api.client.post(f"{API}/sensor/readings", json=reading(device="made-up"), headers=H)
    assert r.status_code == 422 and stored_sensor_rows(api) == []


@pytest.mark.parametrize("level", ["-101", "1001", "Infinity", "NaN"])
def test_sensor_level_is_bounded_and_finite(api, level):
    body = '{"device_id": "sensor-1", "simulated": false, "level_cm": %s}' % level
    r = api.client.post(f"{API}/sensor/readings", content=body, headers={**H, "Content-Type": "application/json"})
    assert r.status_code == 422


def test_sensor_validates_the_body(api):
    assert api.client.post(f"{API}/sensor/readings", json={"device_id": "x"}, headers=H).status_code == 422


def test_same_device_and_time_is_409_not_500(api, monkeypatch):
    from floodready.api import answers
    monkeypatch.setattr(answers, "now_myt", lambda: datetime(2026, 10, 18, 12, 0))
    assert api.client.post(f"{API}/sensor/readings", json=reading(), headers=H).status_code == 204
    assert api.client.post(f"{API}/sensor/readings", json=reading(), headers=H).status_code == 409


def test_real_sensor_above_threshold_confirms_recent_alert_once(api):
    aid = api.alert(at=now_myt().replace(microsecond=0) - timedelta(minutes=10))
    api.client.post(f"{API}/sensor/readings", json=reading(3.0), headers=H)
    assert api.calls == []
    api.client.post(f"{API}/sensor/readings", json=reading(60.0), headers=H)
    api.client.post(f"{API}/sensor/readings", json=reading(70.0, device="sensor-2"), headers=H)
    assert [c["alert_id"] for c in api.calls] == [aid]
    with api.engine.begin() as c:
        assert repo.list_alerts(c)[0]["outcome"] == "confirmed"


def test_sensor_only_confirms_alerts_on_its_own_streets(api):
    api.alert(street="BBR-safe-street", at=now_myt().replace(microsecond=0) - timedelta(minutes=10))
    api.client.post(f"{API}/sensor/readings", json=reading(60.0), headers=H)         # sensor-1 speaks for STREET
    assert api.calls == []
    with api.engine.begin() as c:
        assert repo.list_alerts(c, street_id="BBR-safe-street")[0]["outcome"] == "unverified"


def test_simulated_sensor_never_affects_a_live_alert(api):
    api.alert(at=now_myt().replace(microsecond=0) - timedelta(minutes=10))
    api.client.post(f"{API}/sensor/readings", json=reading(60.0, True, "sim-1"), headers=H)
    assert api.calls == []
    with api.engine.begin() as c:
        assert repo.list_alerts(c)[0]["outcome"] == "unverified"


def test_simulated_sensor_confirms_a_replay_alert(api):
    api.alert(is_replay=True, at=datetime(2024, 11, 12, 9, 0))
    api.client.post(f"{API}/sensor/readings", json=reading(60.0, True, "sim-1"), headers=H)
    with api.engine.begin() as c:
        assert repo.list_alerts(c)[0]["outcome"] == "confirmed"
        assert repo.list_alerts(c, count_simulated_sensor=False)[0]["outcome"] == "unverified"
    assert api.calls == []


# ---------- hardening ----------

def png_bytes(size, mode="L"):
    buf = io.BytesIO()
    Image.new(mode, size).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def test_decompression_bomb_is_rejected_cheaply(api):
    bomb = png_bytes((12000, 12000))
    assert len(bomb) < 1_000_000
    r = api.post(answer="report", files={"photo": ("b.png", bomb, "image/png")})
    assert r.status_code == 422 and api.rows() == []


def test_image_between_the_limit_and_pillows_bomb_error_is_also_rejected(api):
    r = api.post(answer="report", files={"photo": ("b.png", png_bytes((7000, 7000)), "image/png")})   # 49 MP > 40 MP
    assert r.status_code == 422


def test_only_web_formats_are_decoded(api):
    eps = b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\n"
    assert api.post(answer="report", files={"photo": ("a.jpg", eps, "image/jpeg")}).status_code == 422
    bmp = io.BytesIO()
    Image.new("RGB", (4, 4)).save(bmp, "BMP")
    assert api.post(answer="report", files={"photo": ("a.jpg", bmp.getvalue(), "image/jpeg")}).status_code == 422


def test_orientation_is_baked_in_before_exif_is_dropped(api):
    img = Image.new("RGB", (40, 20), (255, 0, 0))
    ex = Image.Exif()
    ex[0x0112] = 6                                        # displayed rotated 90 degrees
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=ex)
    api.post(answer="report", files={"photo": ("a.jpg", buf.getvalue(), "image/jpeg")})
    with Image.open(api.uploads / api.rows()[0]["photo_path"]) as out:
        assert out.size == (20, 40) and len(out.getexif()) == 0


def test_oversized_body_is_rejected_before_parsing(api):
    big = b"\xff\xd8" + b"0" * (12 * 1024 * 1024)
    r = api.post(answer="report", files={"photo": ("big.jpg", big, "image/jpeg")})
    assert r.status_code == 413 and "too large" in r.json()["detail"]


def test_backfill_alerts_cannot_be_answered(api):
    with api.engine.begin() as c:
        [aid] = repo.insert_alerts(c, [make_alert()], is_replay=False, is_backfill=True)
    assert api.post(alert_id=aid).status_code == 422


def test_reports_sent_during_replay_are_demo(api):
    token = api.client.post(f"{API}/admin/login", json={"email": "admin@test", "password": "secret"}).json()["token"]
    api.client.post(f"{API}/admin/replay", json={"event": "2024-11-12", "speed": 0, "stop_at": "09:00"},
                    headers={"Authorization": f"Bearer {token}"})
    api.post(answer="report")
    assert api.rows()[0]["source"] == "demo"


def test_answers_are_rate_limited_per_ip(api):
    codes = [api.post(device=f"d{i}", answer="report").status_code for i in range(12)]
    assert codes[:10] == [200] * 10 and codes[10:] == [429, 429]


# ---------- scripts/sim_sensor.py ----------

def load_sim():
    spec = importlib.util.spec_from_file_location("sim_sensor", ROOT / "scripts" / "sim_sensor.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rise_curve_goes_from_dry_to_above_the_threshold():
    sim = load_sim()
    levels = sim.curve("rise", 10)
    assert len(levels) == 10 and levels == sorted(levels) and levels[0] < 15 < levels[-1]
    assert max(sim.curve("flat", 5)) < 15


def test_sim_sensor_posts_simulated_readings_with_the_token():
    sim = load_sim()
    sent = []

    class Resp:
        status_code = 204

        def raise_for_status(self):
            pass

    def fake_post(url, json, headers, timeout):
        sent.append((url, json, headers))
        return Resp()

    n = sim.run(["--curve", "rise", "--steps", "4", "--interval", "0", "--url", "http://x/api/v1", "--token", "tok"],
                post=fake_post, sleep=lambda s: None)
    assert n == 4
    assert all(u == "http://x/api/v1/sensor/readings" for u, _, _ in sent)
    assert all(j["simulated"] is True and j["device_id"].startswith("sim-") for _, j, _ in sent)
    assert all(h["Authorization"] == "Bearer tok" for _, _, h in sent)
