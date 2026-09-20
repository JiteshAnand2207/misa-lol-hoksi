"""ask_anything — the "ask" feature.

Owner routes live under /me/asks so the legacy dashboard (v2.js) can talk to
them unchanged; the public submission route lives under /profile so profiles
can receive questions from visitors.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.core import rate_limit as rate_limit_mod
from app.core.profiles import resolve_public_profile
from app.db import features_db
from app.models import User
from app.api.v1.profile import require_user

router = APIRouter(prefix="/me", tags=["asks"])
public_router = APIRouter(prefix="/profile", tags=["asks"])

MAX_QUESTION = 400
MAX_AUTHOR = 48
MAX_ANSWER = 2000


def _asks_api_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Ask storage is temporarily unavailable. Please try again.")


@router.get("/asks")
async def my_asks(user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        inbox = await features_db.list_owner_asks(user.id)
    except RuntimeError:
        raise _asks_api_error() from None
    return inbox


@router.post("/asks/{ask_id}/answer")
async def answer_ask(ask_id: str, payload: dict[str, Any], user: User = Depends(require_user)) -> dict[str, Any]:
    answer = str((payload or {}).get("answer") or "").strip()
    if not answer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Write an answer first.")
    answer = answer[:MAX_ANSWER]
    try:
        if await features_db.get_ask(user.id, ask_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ask not found.")
        updated = await features_db.edit_answer(user.id, ask_id, answer) or await features_db.answer_ask(user.id, ask_id, answer)
    except HTTPException:
        raise
    except RuntimeError:
        raise _asks_api_error() from None
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ask not found.")
    return {"ok": True, "ask": updated}


@router.delete("/asks/{ask_id}")
async def delete_ask(ask_id: str, user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        removed = await features_db.delete_ask(user.id, ask_id)
    except RuntimeError:
        raise _asks_api_error() from None
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ask not found.")
    return {"ok": True}


@public_router.post("/{username}/asks", response_model=None)
async def submit_ask(username: str, request: Request) -> dict[str, Any] | RedirectResponse:
    handle = username.strip().lower()
    if not handle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    profile = await resolve_public_profile(handle)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    settings = profile.get("settings") or {}
    if not settings.get("asks"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This profile does not accept questions.")

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

    question = str(body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Type in a question first.")
    if len(question) > MAX_QUESTION:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That question is a little long — keep it under 400 characters.")
    author = str(body.get("author") or "").strip()[:MAX_AUTHOR]

    await rate_limit_mod.rate_limit(f"rl:ask:{handle}:{rate_limit_mod.client_ip(request)}", 3, 60)
    await rate_limit_mod.rate_limit(f"rl:ask:{rate_limit_mod.client_ip(request)}", 30, 600)

    try:
        from app.features import common
        owner_id = str(profile.get("profile", {}).get("uid") or settings.get("uid") or "")
        question = common.plain_text(question, MAX_QUESTION) or question[:MAX_QUESTION]
        await features_db.create_ask(
            owner_id,
            question,
            author=common.plain_text(author, MAX_AUTHOR),
            ip=rate_limit_mod.client_ip(request),
        )
    except RuntimeError:
        raise _asks_api_error() from None

    wants_html = "text/html" in (request.headers.get("accept") or "")
    if wants_html:
        return RedirectResponse(f"/{handle}?sent=1", status_code=status.HTTP_302_FOUND)
    return {"ok": True, "sent": True}