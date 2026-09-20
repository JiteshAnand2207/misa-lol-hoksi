import pytest
from fastapi.testclient import TestClient

import app.api.v1.tally as tally_mod
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


TALLY_RESOLVE = {"profile": {"username": "odt", "uid": "u1"}, "settings": {"tally": {"q": "best otter?", "options": ["river", "pond", "loch"]}}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}


def test_public_vote_json(client, monkeypatch):
    captured = {}

    async def fake_resolve(username):
        return TALLY_RESOLVE

    async def fake_has_vote(owner_id, ip_hash):
        captured["ip_hash"] = ip_hash
        return False

    async def fake_add(owner_id, option, ip=""):
        captured["option"] = option
        return {"options": [], "total": 1}

    async def fake_rate_limit(key, limit, window):
        return None

    monkeypatch.setattr(tally_mod, "resolve_public_profile", fake_resolve)
    monkeypatch.setattr(tally_mod.features_db, "has_tally_vote", fake_has_vote)
    monkeypatch.setattr(tally_mod.features_db, "add_tally_vote", fake_add)
    monkeypatch.setattr(tally_mod.rate_limit_mod, "rate_limit", fake_rate_limit)
    monkeypatch.setattr(tally_mod.rate_limit_mod, "client_ip", lambda request: "1.2.3.4")

    response = client.post("/api/v1/profile/odt/tally", json={"option": "poND"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "option": "pond", "total": 1}
    assert captured["option"] == "pond"


def test_vote_unknown_option_rejected(client, monkeypatch):
    async def fake_resolve(username):
        return TALLY_RESOLVE
    monkeypatch.setattr(tally_mod, "resolve_public_profile", fake_resolve)
    response = client.post("/api/v1/profile/odt/tally", json={"option": "sea"})
    assert response.status_code == 400


def test_duplicate_vote_conflict(client, monkeypatch):
    async def fake_resolve(username):
        return TALLY_RESOLVE
    async def fake_has_vote(owner_id, ip_hash):
        return True
    async def fake_rate_limit(key, limit, window):
        return None
    monkeypatch.setattr(tally_mod, "resolve_public_profile", fake_resolve)
    monkeypatch.setattr(tally_mod.features_db, "has_tally_vote", fake_has_vote)
    monkeypatch.setattr(tally_mod.rate_limit_mod, "rate_limit", fake_rate_limit)
    monkeypatch.setattr(tally_mod.rate_limit_mod, "client_ip", lambda request: "1.2.3.4")
    response = client.post("/api/v1/profile/odt/tally", json={"option": "river"})
    assert response.status_code == 409


def test_tally_disabled_404(client, monkeypatch):
    async def fake_resolve(username):
        return {"profile": {"username": "odt", "uid": "u1"}, "settings": {"tally": {"q": "", "options": []}}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}
    monkeypatch.setattr(tally_mod, "resolve_public_profile", fake_resolve)
    assert client.post("/api/v1/profile/odt/tally", json={"option": "river"}).status_code == 404


def test_vote_form_redirects(client, monkeypatch):
    async def fake_resolve(username):
        return TALLY_RESOLVE
    async def fake_has_vote(owner_id, ip_hash):
        return False
    async def fake_add(owner_id, option, ip=""):
        return {"options": [], "total": 3}
    async def fake_rate_limit(key, limit, window):
        return None
    monkeypatch.setattr(tally_mod, "resolve_public_profile", fake_resolve)
    monkeypatch.setattr(tally_mod.features_db, "has_tally_vote", fake_has_vote)
    monkeypatch.setattr(tally_mod.features_db, "add_tally_vote", fake_add)
    monkeypatch.setattr(tally_mod.rate_limit_mod, "rate_limit", fake_rate_limit)
    monkeypatch.setattr(tally_mod.rate_limit_mod, "client_ip", lambda request: "1.2.3.4")
    response = client.post(
        "/api/v1/profile/odt/tally",
        data={"option": "river"},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/odt?tallied=1" in response.headers["location"]


def test_clear_my_tally(client, monkeypatch):
    import app.db.features_db as db

    async def fake_clear(owner_id):
        assert owner_id == "u1"
        return True
    monkeypatch.setattr(db, "clear_tally", fake_clear)
    assert client.delete("/api/v1/me/tally").status_code == 200