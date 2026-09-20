"""tally — the visitor poll feature.

Public visitors vote on one of the profile owner's options, once per IP. The
owner can clear the results from the dashboard-free /me route.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.core import rate_limit as rate_limit_mod
from app.core.profiles import resolve_public_profile
from app.db import features_db
from app.models import User
from app.api.v1.profile import require_user

router = APIRouter(prefix="/me", tags=["tally"])
public_router = APIRouter(prefix="/profile", tags=["tally"])


def _tally_api_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Tally storage is temporarily unavailable. Please try again.")


@router.delete("/tally")
async def clear_my_tally(user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        await features_db.clear_tally(user.id)
    except RuntimeError:
        raise _tally_api_error() from None
    return {"ok": True, "total": 0}


@public_router.post("/{username}/tally", response_model=None)
async def submit_vote(username: str, request: Request) -> dict[str, Any]:
    handle = username.strip().lower()
    if not handle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    profile = await resolve_public_profile(handle)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    settings = profile.get("settings") or {}
    tally = settings.get("tally")
    if not isinstance(tally, dict):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This profile is not running a tally.")
    question = str(tally.get("q") or "").strip()
    options = [str(option).strip() for option in (tally.get("options") or []) if str(option).strip()]
    if not question or len(options) < 2:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This profile is not running a tally.")

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

    chosen = str(body.get("option") or "").strip()
    if not chosen:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pick an answer first.")
    match = next((option for option in options if option.lower() == chosen.lower()), None)
    if match is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That is not one of the answers.")

    await rate_limit_mod.rate_limit(f"rl:tally:{handle}:{rate_limit_mod.client_ip(request)}", 5, 60)
    await rate_limit_mod.rate_limit(f"rl:tally:{rate_limit_mod.client_ip(request)}", 60, 600)

    try:
        from app.features import common
        owner_id = str(profile.get("profile", {}).get("uid") or settings.get("uid") or "")
        ip_hash = features_db.hash_ip(rate_limit_mod.client_ip(request)) if rate_limit_mod.client_ip(request) else ""
        if await features_db.has_tally_vote(owner_id, ip_hash):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already voted on this tally.")
        totals = await features_db.add_tally_vote(owner_id, common.plain_text(match, 80), ip=rate_limit_mod.client_ip(request))
    except HTTPException:
        raise
    except RuntimeError:
        raise _tally_api_error() from None
    wants_html = "text/html" in (request.headers.get("accept") or "")
    if wants_html:
        return RedirectResponse(f"/{handle}?tallied=1", status_code=status.HTTP_302_FOUND)
    return {"ok": True, "option": match, "total": int(totals.get("total") or 0)}