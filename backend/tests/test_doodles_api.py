import base64

import pytest
from fastapi.testclient import TestClient

import app.api.v1.doodles as doodles_mod
from app.api.v1.doodles import validate_doodle_svg
from app.api.v1.profile import require_user
from app.main import create_app
from app.models import User

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def client():
    app = create_app()

    def override():
        return User(id="u1", username="odt", display_name="Otter", created_at="2025-01-01")

    app.dependency_overrides[require_user] = override
    return TestClient(app, base_url="https://misa.lol")


def test_validate_doodle_accepts_png_data_url():
    data = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode()
    assert validate_doodle_svg(data) == data


def test_validate_doodle_rejects_bogus_tokens():
    assert validate_doodle_svg("<svg><script>alert(1)</script></svg>") is None
    assert validate_doodle_svg("data:image/png;base64,no!!") is None
    assert validate_doodle_svg("") is None


def test_validate_doodle_accepts_plain_svg():
    assert validate_doodle_svg("<svg><circle r=\"10\"/></svg>") == "<svg><circle r=\"10\"/></svg>"


def test_owner_doodles_inbox(client, monkeypatch):
    import app.db.features_db as db

    async def fake_bucket(owner_id):
        assert owner_id == "u1"
        return {"pending": [{"id": "d1", "svg": "<svg/>", "at": "2025-01-01T00:00:00Z"}], "approved": []}

    monkeypatch.setattr(db, "list_owner_doodles", fake_bucket)
    response = client.get("/api/v1/me/doodles")
    assert response.status_code == 200
    assert response.json()["pending"][0]["svg"] == "<svg/>"


def test_owner_approve_doodle(client, monkeypatch):
    import app.db.features_db as db

    async def fake_approve(owner_id, doodle_id):
        assert doodle_id == "d1"
        return {"id": "d1", "svg": "<svg/>", "at": "2025-01-01T00:00:00Z"}

    monkeypatch.setattr(db, "approve_doodle", fake_approve)
    assert client.post("/api/v1/me/doodles/d1/approve").status_code == 200


def test_owner_bin_doodle(client, monkeypatch):
    import app.db.features_db as db
    async def fake_delete(owner_id, doodle_id):
        return True
    monkeypatch.setattr(db, "delete_doodle", fake_delete)
    assert client.delete("/api/v1/me/doodles/d1").status_code == 200


def test_public_submit_json(client, monkeypatch):
    captured = {}
    data = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode()

    async def fake_resolve(username):
        return {"profile": {"username": "odt", "uid": "u1"}, "settings": {"doodles": True}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}

    async def fake_create(owner_id, svg, ip=""):
        captured["owner"] = owner_id
        captured["svg"] = svg
        captured["ip"] = ip
        return {"id": "n1"}

    async def fake_rate_limit(key, limit, window):
        return None

    monkeypatch.setattr(doodles_mod, "resolve_public_profile", fake_resolve)
    monkeypatch.setattr(doodles_mod.features_db, "create_doodle", fake_create)
    monkeypatch.setattr(doodles_mod.rate_limit_mod, "rate_limit", fake_rate_limit)
    monkeypatch.setattr(doodles_mod.rate_limit_mod, "client_ip", lambda request: "1.2.3.4")

    response = client.post("/api/v1/profile/odt/doodles", json={"svg": data})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "sent": True}
    assert captured["owner"] == "u1"
    assert captured["svg"] == data


def test_public_submit_invalid_rejected(client, monkeypatch):
    async def fake_resolve(username):
        return {"profile": {"username": "odt", "uid": "u1"}, "settings": {"doodles": True}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}
    monkeypatch.setattr(doodles_mod, "resolve_public_profile", fake_resolve)
    hashes = "data:image/png;base64,dGVzdA=="
    assert client.post("/api/v1/profile/odt/doodles", json={"svg": hashes}).status_code == 400
    assert client.post("/api/v1/profile/odt/doodles", json={"svg": "<svg><script>x</script></svg>"}).status_code == 400


def test_public_disabled_404(client, monkeypatch):
    async def fake_resolve(username):
        return {"profile": {"username": "odt", "uid": "u1"}, "settings": {"doodles": False}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}
    monkeypatch.setattr(doodles_mod, "resolve_public_profile", fake_resolve)
    assert client.post("/api/v1/profile/odt/doodles", json={"svg": "<svg/>"}).status_code == 404