import pytest
from fastapi.testclient import TestClient

import app.api.v1.guestbooks as gb_mod
from app.api.v1.profile import require_user
from app.main import create_app
from app.models import User


@pytest.fixture
def client():
    app = create_app()

    def override():
        return User(id="u1", username="odt", display_name="Otter", created_at="2025-01-01")

    app.dependency_overrides[require_user] = override
    return TestClient(app, base_url="https://misa.lol")


def test_owner_guestbook_inbox(client, monkeypatch):
    import app.db.features_db as db

    async def fake_bucket(owner_id):
        assert owner_id == "u1"
        return {"pending": [{"id": "s1", "line": "hello", "name": "Sam", "at": "2025-01-01T00:00:00Z"}], "approved": []}

    monkeypatch.setattr(db, "list_owner_guestbook", fake_bucket)
    response = client.get("/api/v1/me/guestbook")
    assert response.status_code == 200
    assert response.json()["pending"][0]["line"] == "hello"


def test_owner_approve_signature(client, monkeypatch):
    import app.db.features_db as db

    async def fake_approve(owner_id, signature_id):
        assert owner_id == "u1"
        assert signature_id == "s1"
        return {"id": "s1", "line": "hello", "name": "Sam", "at": "2025-01-01T00:00:00Z"}

    monkeypatch.setattr(db, "approve_signature", fake_approve)
    response = client.post("/api/v1/me/guestbook/s1/approve")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_owner_bin_signature(client, monkeypatch):
    import app.db.features_db as db

    async def fake_delete(owner_id, signature_id):
        return True

    monkeypatch.setattr(db, "delete_signature", fake_delete)
    assert client.delete("/api/v1/me/guestbook/s1").status_code == 200
    async def fake_missing(owner_id, signature_id):
        return False
    monkeypatch.setattr(db, "delete_signature", fake_missing)
    assert client.delete("/api/v1/me/guestbook/s2").status_code == 404


def test_public_submit_json(client, monkeypatch):
    import app.db.features_db as db

    captured = {}

    async def fake_resolve(username):
        assert username == "odt"
        return {"profile": {"username": "odt", "uid": "u1"}, "settings": {"guestbook": True}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}

    async def fake_create(owner_id, line, name="", ip=""):
        captured["owner"] = owner_id
        captured["line"] = line
        captured["name"] = name
        captured["ip"] = ip
        return {"id": "n1"}

    async def fake_rate_limit(key, limit, window):
        captured["rl"] = key

    monkeypatch.setattr(gb_mod.features_db, "create_signature", fake_create)
    monkeypatch.setattr(gb_mod.rate_limit_mod, "rate_limit", fake_rate_limit)
    monkeypatch.setattr(gb_mod.rate_limit_mod, "client_ip", lambda request: "1.2.3.4")
    monkeypatch.setattr(gb_mod, "resolve_public_profile", fake_resolve)

    response = client.post("/api/v1/profile/odt/guestbook", json={"line": "hi from api", "name": "Sam"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "sent": True}
    assert captured["owner"] == "u1"
    assert captured["line"] == "hi from api"
    assert captured["name"] == "Sam"
    assert captured["ip"] == "1.2.3.4"


def test_public_submit_disabled_404(client, monkeypatch):
    import app.db.features_db as db

    async def fake_resolve(username):
        return {"profile": {"username": "odt", "uid": "u1"}, "settings": {"guestbook": False}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}

    monkeypatch.setattr(gb_mod, "resolve_public_profile", fake_resolve)
    response = client.post("/api/v1/profile/odt/guestbook", json={"line": "hello?"})
    assert response.status_code == 404


def test_public_submit_blank_lines_rejected(client, monkeypatch):
    async def fake_resolve(username):
        return {"profile": {"username": "odt", "uid": "u1"}, "settings": {"guestbook": True}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}

    monkeypatch.setattr(gb_mod, "resolve_public_profile", fake_resolve)
    response = client.post("/api/v1/profile/odt/guestbook", json={"line": "   "})
    assert response.status_code == 400


def test_public_submit_form_redirects(client, monkeypatch):
    async def fake_resolve(username):
        return {"profile": {"username": "odt", "uid": "u1"}, "settings": {"guestbook": True}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}

    async def fake_create(*args, **kwargs):
        return {"id": "n1"}

    async def fake_rate_limit(key, limit, window):
        return None

    monkeypatch.setattr(gb_mod, "resolve_public_profile", fake_resolve)
    monkeypatch.setattr(gb_mod.features_db, "create_signature", fake_create)
    monkeypatch.setattr(gb_mod.rate_limit_mod, "rate_limit", fake_rate_limit)
    monkeypatch.setattr(gb_mod.rate_limit_mod, "client_ip", lambda request: "1.2.3.4")

    response = client.post(
        "/api/v1/profile/odt/guestbook",
        data={"line": "hi from form"},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/odt?signed=1" in response.headers["location"]