"""secret — the word-locked reveal.

The owner stores ``{word, wordHash, url, label, hasSecret}`` in raw
``settings.secret``. The public stripped copy (``stripped_secret``) exposes
only ``hasSecret`` and blank values, so nothing — not the word, not the hash,
not the url, not the label — is ever served to a plain visitor.

A visitor may attempt a reveal by sending a single word. The comparison is
done server-side against the owner's raw stored ``wordHash`` (a SHA-256 of the
word) using a constant-time compare; on a match the ``url`` and ``label`` are
returned. The word and the hash are never returned by any response — not even
on a match. Attempts are rate-limited per profile and per IP so the hash
cannot be brute-forced through this endpoint.
"""

import hashlib
import secrets as secrets_clib
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.core import rate_limit as rate_limit_mod
from app.core.profiles import resolve_public_profile, unwrap_profile_config
from app.db import data_api

public_router = APIRouter(prefix="/profile", tags=["secret"])


def _sha256(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


async def _owner_raw_secret(profile: dict[str, Any]) -> dict[str, Any]:
    """Server-side raw secret block from the owner's stored config.

    This is the ONLY place the hashes/urls/labels are read for the reveal; it
    must never be returned to a visitor. Callers must strip the word+wordHash
    before serialising anything to a response.
    """
    owner_id = str(profile.get("profile", {}).get("uid") or "")
    if not owner_id:
        return {}
    stored = await data_api.get_profile(owner_id)
    raw = unwrap_profile_config(stored) or {}
    settings = raw.get("settings") if isinstance(raw.get("settings"), dict) else {}
    secret = settings.get("secret") if isinstance(settings.get("secret"), dict) else {}
    return secret


@public_router.post("/{username}/reveal", response_model=None)
async def reveal_secret(username: str, request: Request) -> dict[str, Any]:
    handle = username.strip().lower()
    if not handle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    profile = await resolve_public_profile(handle)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    settings = profile.get("settings") or {}
    secret_public = settings.get("secret") if isinstance(settings.get("secret"), dict) else {}
    if not secret_public.get("hasSecret"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This profile has no secret to reveal.")

    ip = rate_limit_mod.client_ip(request)
    await rate_limit_mod.rate_limit(f"rl:reveal:{handle}:{ip}", 5, 60)
    await rate_limit_mod.rate_limit(f"rl:reveal:{ip}", 15, 600)

    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    body: dict[str, Any] = {}
    if content_type == "application/json":
        try:
            payload = await request.json()
        except Exception:
            payload = None
        if isinstance(payload, dict):
            body = payload
    else:
        form = await request.form()
        body = {key: str(value) for key, value in form.items()}

    word = str(body.get("word") or "").strip()
    if not word:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Send a word first.")
    if len(word) > 120:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That word is too long.")

    owner_secret = await _owner_raw_secret(profile)
    stored_hash = str(owner_secret.get("wordHash") or "")
    if not stored_hash:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No secret word is configured on this profile.")

    attempt_hash = _sha256(word)
    if not secrets_clib.compare_digest(attempt_hash, stored_hash):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="That word does not unlock this secret.")

    return {
        "ok": True,
        "revealed": True,
        "url": str(owner_secret.get("url") or "").strip(),
        "label": str(owner_secret.get("label") or "").strip(),
    }
