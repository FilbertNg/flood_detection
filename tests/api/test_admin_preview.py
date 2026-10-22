"""Read-only Admin preview without an account (ADMIN_PREVIEW=1): what it can and cannot reach."""
import pytest
from fastapi.testclient import TestClient

from floodready.api import auth
from floodready.api.main import create_app

API = "/api/v1"
SECRET = "test-secret-that-is-at-least-32-bytes-long"


@pytest.fixture()
def make_client(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("EVENTS_CSV", str(tmp_path / "events.csv"))
    for var in ("ADMIN_EMAIL", "ADMIN_PASSWORD", "ADMIN_PREVIEW", "FLOODREADY_DEV_LOGIN"):
        monkeypatch.delenv(var, raising=False)
    (tmp_path / "uploads").mkdir()
    with runner.db.begin() as c:
        auth.create_user(c, "boss@test", "pw-boss-12345", "admin")

    def make(preview: bool):
        if preview:
            monkeypatch.setenv("ADMIN_PREVIEW", "1")
        return TestClient(create_app(runner, start_live_loop=False))
    return make


def preview_headers(client):
    r = client.post(f"{API}/admin/preview")
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"token"}
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_preview_is_off_unless_switched_on(make_client):
    with make_client(preview=False) as client:
        assert client.post(f"{API}/admin/preview").status_code == 404


def test_preview_needs_a_signing_secret(make_client, monkeypatch):
    monkeypatch.delenv("JWT_SECRET")
    with make_client(preview=True) as client:
        assert client.post(f"{API}/admin/preview").status_code == 503


def test_preview_token_reads_statistics_reports_and_suggestions(make_client):
    with make_client(preview=True) as client:
        h = preview_headers(client)
        for path in ("/admin/stats?from=2024-11-01&to=2024-11-30", "/admin/report?month=2024-11", "/admin/suggestions"):
            assert client.get(f"{API}{path}", headers=h).status_code == 200, path


def test_preview_cannot_see_residents_answers(make_client):
    """Answers carry device ids, photos and locations: never shown to an anonymous preview."""
    with make_client(preview=True) as client:
        r = client.get(f"{API}/admin/answers", headers=preview_headers(client))
        assert r.status_code == 403


@pytest.mark.parametrize("method,path,body", [
    ("PATCH", "/admin/suggestions/s1", {"status": "accepted"}),
    ("PATCH", "/admin/answers/a1", {"review_status": "accepted"}),
    ("POST", "/admin/notes", {"street_id": "BBR-prone-street", "text": "x"}),
    ("POST", "/admin/replay", {"event": "2024-11-12"}),
    ("DELETE", "/admin/replay", None),
])
def test_preview_cannot_write(make_client, method, path, body):
    with make_client(preview=True) as client:
        r = client.request(method, f"{API}{path}", headers=preview_headers(client), json=body)
        assert r.status_code == 403


def test_preview_token_stops_working_when_preview_is_switched_off(make_client, monkeypatch):
    with make_client(preview=True) as client:
        h = preview_headers(client)
        monkeypatch.delenv("ADMIN_PREVIEW")
        assert client.get(f"{API}/admin/suggestions", headers=h).status_code == 401


def test_admins_still_see_answers_with_preview_on(make_client):
    with make_client(preview=True) as client:
        r = client.post(f"{API}/admin/login", json={"email": "boss@test", "password": "pw-boss-12345"})
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        assert client.get(f"{API}/admin/answers", headers=h).status_code == 200
