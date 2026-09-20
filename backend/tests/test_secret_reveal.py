import hashlib

import httpx
import pytest

import app.api.v1.secret_reveal as secret_reveal_mod
from app.main import create_app

HANDLE = "otter"
WORD = "otter"
WORD_HASH = hashlib.sha256(WORD.encode("utf-8")).hexdigest()


async def _resolve_fake(username):
    return {
        "profile": {"username": HANDLE, "uid": "u1"},
        "settings": {"secret": {"hasSecret": True, "word": "", "wordHash": "", "url": "", "label": ""}},
        "assets": {},
        "socials": [],
        "badges": [],
        "widgets": [],
        "sections": [],
    }


async def _raw_profile_fake(owner_id):
    return {
        "config": {
            "profile": {"username": HANDLE, "uid": owner_id},
            "settings": {
                "secret": {"hasSecret": True, "word": WORD, "wordHash": WORD_HASH, "url": "https://secret.example/hideout", "label": "Secret hideout"}
            },
        }
    }


@pytest.mark.asyncio
async def test_reveal_correct_word_never_returns_word_or_hash(monkeypatch):
    async def _rate_limit_fake(key, limit, window):
        return None

    monkeypatch.setattr(secret_reveal_mod, "resolve_public_profile", _resolve_fake)
    monkeypatch.setattr(secret_reveal_mod.data_api, "get_profile", _raw_profile_fake)
    monkeypatch.setattr(secret_reveal_mod.rate_limit_mod, "rate_limit", _rate_limit_fake)
    monkeypatch.setattr(secret_reveal_mod.rate_limit_mod, "client_ip", lambda request: "1.2.3.4")

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://misa.lol") as client:
        resp = await client.post(f"/api/v1/profile/{HANDLE}/reveal", json={"word": WORD})

    assert resp.status_code == 200
    raw = resp.text
    data = resp.json()
    assert data["ok"] is True
    assert "url" in data and data["url"] == "https://secret.example/hideout"
    assert "label" in data and data["label"] == "Secret hideout"
    assert "otter" not in raw
    assert "wordHash" not in raw
    assert "word" not in raw


@pytest.mark.asyncio
async def test_reveal_wrong_word_404_and_no_leak(monkeypatch):
    async def _rate_limit_fake(key, limit, window):
        return None

    monkeypatch.setattr(secret_reveal_mod, "resolve_public_profile", _resolve_fake)
    monkeypatch.setattr(secret_reveal_mod.data_api, "get_profile", _raw_profile_fake)
    monkeypatch.setattr(secret_reveal_mod.rate_limit_mod, "rate_limit", _rate_limit_fake)
    monkeypatch.setattr(secret_reveal_mod.rate_limit_mod, "client_ip", lambda request: "1.2.3.4")

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://misa.lol") as client:
        resp = await client.post(f"/api/v1/profile/{HANDLE}/reveal", json={"word": "wrong"})

    assert resp.status_code == 404
    raw = resp.text
    assert WORD_HASH not in raw
    assert "otter" not in raw