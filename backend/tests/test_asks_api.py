import pytest
from fastapi.testclient import TestClient

from app.api.v1.profile import require_user
from app.db import features_db
from app.main import create_app
from app.models import User


def fake_user() -> User:
    return User(id="u1", username="odt", display_name="Otter", created_at="2025-01-01")


@pytest.fixture
def client(monkeypatch):
    app = create_app()
    app.dependency_overrides[require_user] = fake_user
    test_client = TestClient(app, base_url="https://misa.lol")
    yield test_client, monkeypatch
    app.dependency_overrides.clear()
    test_client.close()


def patch_db(monkeypatch, **fakes) -> None:
    for name, fake in fakes.items():
        monkeypatch.setattr(features_db, name, fake)


def test_owner_asks_inbox(client):
    c, mp = client
    async def fake_list(user_id):
        assert user_id == "u1"
        return {
            "waiting": [{"id": "w1", "q": "hello?", "a": "", "status": "pending", "at": "2025-01-01T00:00:00Z"}],
            "answered": [{"id": "a1", "q": "why?", "a": "because", "status": "published", "at": "2025-01-02T00:00:00Z"}],
        }
    patch_db(mp, list_owner_asks=fake_list)
    response = c.get("/api/v1/me/asks")
    assert response.status_code == 200
    data = response.json()
    assert data["waiting"][0]["q"] == "hello?"
    assert data["answered"][0]["a"] == "because"


def test_owner_answer_publishes(client):
    c, mp = client
    calls = {}

    async def fake_get(user_id, ask_id):
        return {"id": ask_id, "q": "hello?", "a": "", "status": "pending", "at": ""}

    async def fake_answer(user_id, ask_id, answer):
        calls["answer"] = (user_id, ask_id, answer)
        return {"id": ask_id, "q": "hello?", "a": answer, "status": "published", "at": ""}

    async def fake_edit(user_id, ask_id, answer):
        calls["edit"] = (user_id, ask_id, answer)
        return None

    patch_db(mp, get_ask=fake_get, answer_ask=fake_answer, edit_answer=fake_edit)
    response = c.post("/api/v1/me/asks/w1/answer", json={"answer": "because"})
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert calls["answer"] == ("u1", "w1", "because")


def test_owner_answer_empty_rejected(client):
    c, mp = client
    patch_db(mp, get_ask=lambda *a, **k: {"id": "w1"})
    response = c.post("/api/v1/me/asks/w1/answer", json={"answer": "   "})
    assert response.status_code == 400


def test_owner_bin_ask(client):
    c, mp = client
    calls = {}

    async def fake_delete(user_id, ask_id):
        calls["delete"] = (user_id, ask_id)
        return True

    patch_db(mp, delete_ask=fake_delete)
    response = c.delete("/api/v1/me/asks/w1")
    assert response.status_code == 200
    assert calls["delete"] == ("u1", "w1")


def test_public_submit_json(client):
    import app.api.v1.asks as asks_mod

    c, mp = client
    captured = {}

    async def fake_resolve(username):
        assert username == "odt"
        return {"profile": {"username": "odt", "uid": "u1"}, "settings": {"asks": True}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}

    async def fake_create(owner_id, question, author="", ip=""):
        captured["owner"] = owner_id
        captured["question"] = question
        captured["author"] = author
        captured["ip"] = ip
        return {"id": "n1"}

    async def fake_rate_limit(key, limit, window):
        captured["rl"] = key

    mp.setattr(asks_mod.features_db, "create_ask", fake_create)
    mp.setattr(asks_mod.rate_limit_mod, "rate_limit", fake_rate_limit)
    mp.setattr(asks_mod.rate_limit_mod, "client_ip", lambda request: "1.2.3.4")
    mp.setattr(asks_mod, "resolve_public_profile", fake_resolve)

    response = c.post("/api/v1/profile/odt/asks", json={"question": "hello?", "author": "Sam"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "sent": True}
    assert captured["owner"] == "u1"
    assert captured["question"] == "hello?"
    assert captured["author"] == "Sam"
    assert captured["ip"] == "1.2.3.4"


def test_public_submit_disabled_404(client):
    import app.api.v1.asks as asks_mod

    c, mp = client

    async def fake_resolve(username):
        return {"profile": {"username": "odt", "uid": "u1"}, "settings": {"asks": False}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}

    mp.setattr(asks_mod, "resolve_public_profile", fake_resolve)
    response = c.post("/api/v1/profile/odt/asks", json={"question": "hello?"})
    assert response.status_code == 404


def test_public_submit_form_redirects(client):
    import app.api.v1.asks as asks_mod

    c, mp = client

    async def fake_resolve(username):
        return {"profile": {"username": "odt", "uid": "u1"}, "settings": {"asks": True}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}

    async def fake_create(*args, **kwargs):
        return {"id": "n1"}

    async def fake_rate_limit(key, limit, window):
        return None

    mp.setattr(asks_mod, "resolve_public_profile", fake_resolve)
    mp.setattr(asks_mod.features_db, "create_ask", fake_create)
    mp.setattr(asks_mod.rate_limit_mod, "rate_limit", fake_rate_limit)
    mp.setattr(asks_mod.rate_limit_mod, "client_ip", lambda request: "1.2.3.4")

    response = c.post(
        "/api/v1/profile/odt/asks",
        data={"question": "hi from form"},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/odt?sent=1" in response.headers["location"]


def test_public_submit_blank_question(client):
    import app.api.v1.asks as asks_mod

    c, mp = client

    async def fake_resolve(username):
        return {"profile": {"username": "odt", "uid": "u1"}, "settings": {"asks": True}, "assets": {}, "socials": [], "badges": [], "widgets": [], "sections": []}

    mp.setattr(asks_mod, "resolve_public_profile", fake_resolve)
    response = c.post("/api/v1/profile/odt/asks", json={"question": "   "})
    assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])