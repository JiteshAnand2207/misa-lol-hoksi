"""guestbook — the "visitors book" feature.

Owner routes live under /me/guestbook so the legacy dashboard (v2.js) can talk
to them unchanged; the public signing route lives under /profile so visitors
can sign an approved page.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.core import rate_limit as rate_limit_mod
from app.core.profiles import resolve_public_profile
from app.db import features_db
from app.models import User
from app.api.v1.profile import require_user

router = APIRouter(prefix="/me", tags=["guestbook"])
public_router = APIRouter(prefix="/profile", tags=["guestbook"])

MAX_LINE = 400
MAX_NAME = 48


def _guestbook_api_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Guestbook storage is temporarily unavailable. Please try again.")


@router.get("/guestbook")
async def my_guestbook(user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        return await features_db.list_owner_guestbook(user.id)
    except RuntimeError:
        raise _guestbook_api_error() from None


@router.post("/guestbook/{signature_id}/approve")
async def approve_signature(signature_id: str, user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        updated = await features_db.approve_signature(user.id, signature_id)
    except RuntimeError:
        raise _guestbook_api_error() from None
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signature not found.")
    return {"ok": True, "signature": updated}


@router.delete("/guestbook/{signature_id}")
async def bin_signature(signature_id: str, user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        removed = await features_db.delete_signature(user.id, signature_id)
    except RuntimeError:
        raise _guestbook_api_error() from None
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signature not found.")
    return {"ok": True}


@public_router.post("/{username}/guestbook", response_model=None)
async def submit_signature(username: str, request: Request) -> dict[str, Any] | RedirectResponse:
    handle = username.strip().lower()
    if not handle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    profile = await resolve_public_profile(handle)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    settings = profile.get("settings") or {}
    if not settings.get("guestbook"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This profile does not accept signatures.")

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

    line = str(body.get("line") or body.get("text") or "").strip()
    if not line:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Write something in the book first.")
    if len(line) > MAX_LINE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That line is a little long — keep it under 400 characters.")
    name = str(body.get("name") or "").strip()[:MAX_NAME]

    await rate_limit_mod.rate_limit(f"rl:guest:{handle}:{rate_limit_mod.client_ip(request)}", 3, 60)
    await rate_limit_mod.rate_limit(f"rl:guest:{rate_limit_mod.client_ip(request)}", 30, 600)

    try:
        from app.features import common
        owner_id = str(profile.get("profile", {}).get("uid") or settings.get("uid") or "")
        line = common.plain_text(line, MAX_LINE) or line[:MAX_LINE]
        await features_db.create_signature(
            owner_id,
            line,
            name=common.plain_text(name, MAX_NAME),
            ip=rate_limit_mod.client_ip(request),
        )
    except RuntimeError:
        raise _guestbook_api_error() from None

    wants_html = "text/html" in (request.headers.get("accept") or "")
    if wants_html:
        return RedirectResponse(f"/{handle}?signed=1", status_code=status.HTTP_302_FOUND)
    return {"ok": True, "sent": True}