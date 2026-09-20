"""doodles — the chalkboard feature.

Visitors draw a small picture which is stored as a data URL (PNG or a sanitised
SVG). The owner approves or bins entries from the dashboard board UI
(/me/doodles) which v2.js already talks to unchanged.
"""

import base64
import binascii
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core import rate_limit as rate_limit_mod
from app.core.profiles import resolve_public_profile
from app.db import features_db
from app.models import User
from app.api.v1.profile import require_user

router = APIRouter(prefix="/me", tags=["doodles"])
public_router = APIRouter(prefix="/profile", tags=["doodles"])

MAX_DOODLE_CHARS = 1_500_000
MAX_DOODLE_BYTES = 600_000


def _doodles_api_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Doodle storage is temporarily unavailable. Please try again.")


def validate_doodle_svg(raw: str) -> str | None:
    """Return the doodle payload when it is a safe PNG data URL or trivial SVG."""
    value = str(raw or "").strip()
    if not value:
        return None
    if len(value) > MAX_DOODLE_CHARS:
        return None
    lowered = value.lower()
    if lowered.startswith("data:image/png;base64,"):
        chunk = value.split(",", 1)[1] if "," in value else ""
        if not chunk or len(chunk) > MAX_DOODLE_CHARS or any(ord(character) > 127 for character in chunk):
            return None
        try:
            decoded = base64.b64decode(chunk, validate=True)
        except (binascii.Error, ValueError):
            return None
        if len(decoded) > MAX_DOODLE_BYTES or not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
            return None
        return value
    if lowered.startswith("data:image/svg+xml") or lowered.startswith("<svg"):
        for token in ("<script", "onload=", "onerror=", "javascript:"):
            if token in lowered:
                return None
        return value
    return None


@router.get("/doodles")
async def my_doodles(user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        return await features_db.list_owner_doodles(user.id)
    except RuntimeError:
        raise _doodles_api_error() from None


@router.post("/doodles/{doodle_id}/approve")
async def approve_doodle(doodle_id: str, user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        updated = await features_db.approve_doodle(user.id, doodle_id)
    except RuntimeError:
        raise _doodles_api_error() from None
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doodle not found.")
    return {"ok": True, "doodle": updated}


@router.delete("/doodles/{doodle_id}")
async def bin_doodle(doodle_id: str, user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        removed = await features_db.delete_doodle(user.id, doodle_id)
    except RuntimeError:
        raise _doodles_api_error() from None
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doodle not found.")
    return {"ok": True}


@public_router.post("/{username}/doodles", response_model=None)
async def submit_doodle(username: str, request: Request) -> dict[str, Any]:
    handle = username.strip().lower()
    if not handle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    profile = await resolve_public_profile(handle)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    settings = profile.get("settings") or {}
    if not settings.get("doodles"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This profile does not accept doodles.")

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

    svg = str(body.get("svg") or body.get("data") or "").strip()
    if not svg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Draw something first.")
    validated = validate_doodle_svg(svg)
    if validated is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That doodle could not be saved.")

    await rate_limit_mod.rate_limit(f"rl:doodle:{handle}:{rate_limit_mod.client_ip(request)}", 4, 60)
    await rate_limit_mod.rate_limit(f"rl:doodle:{rate_limit_mod.client_ip(request)}", 20, 600)

    try:
        owner_id = str(profile.get("profile", {}).get("uid") or settings.get("uid") or "")
        await features_db.create_doodle(owner_id, validated, ip=rate_limit_mod.client_ip(request))
    except RuntimeError:
        raise _doodles_api_error() from None
    return {"ok": True, "sent": True}