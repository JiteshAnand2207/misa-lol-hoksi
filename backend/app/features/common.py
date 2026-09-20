"""Shared validation helpers for the misa.lol feature settings.

Kept dependency-free (stdlib only) so the package can be imported and tested
without the application stack.
"""

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

PRINTABLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def plain_text(value: Any, limit: int) -> str:
    """Strip markup and control characters, collapse whitespace, cap length."""
    text = str(value or "")
    text = re.sub(r"<[^>]*>", "", text)
    text = PRINTABLE.sub("", text)
    return " ".join(text.split())[:limit]


def multiline(value: Any, limit: int) -> str:
    """Like plain_text but preserves newlines/tabs."""
    text = str(value or "")
    text = re.sub(r"<[^>]*>", "", text)
    text = PRINTABLE.sub("", text)
    lower = text.lower()
    if "javascript:" in lower or "vbscript:" in lower or "data:text/html" in lower:
        text = re.sub(r"(?i)javascript:|vbscript:|data:text/html", "", text)
    return text[:limit]


def strict_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    return default


def clamp_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def one_of(value: Any, allowed: tuple[str, ...], default: str) -> str:
    return value if value in allowed else default


def is_http_url(value: str) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if parsed.username or parsed.password:
        return False
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        return False
    return True


def parse_iso_utc(value: Any) -> str:
    """Normalise or reject an ISO date-time. Stored as UTC 'YYYY-MM-DDTHH:MM:SSZ'."""
    text = str(value or "").strip()[:40]
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.year < 2000 or parsed.year > 2100:
        return ""
    parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_tz(value: Any) -> str:
    text = str(value or "").strip()[:80]
    if not text:
        return ""
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(text)
    except Exception:
        return ""
    return text