from fastapi import HTTPException, Request, status

from app.db.dragonfly import get_dragonfly


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit(key: str, limit: int, window_seconds: int) -> None:
    redis = get_dragonfly()
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    if count > limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")


async def limit_auth(request: Request, action: str, limit: int = 10, window_seconds: int = 60) -> None:
    await rate_limit(f"rl:{action}:{client_ip(request)}", limit, window_seconds)
