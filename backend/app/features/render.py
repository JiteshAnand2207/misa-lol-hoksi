"""Render-only feature blocks for the public profile.

These features are driven entirely by validated profile settings and need no
extra tables or endpoints: reverse, night, draw, capsule, archive, moon,
neighbours and presence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

from app.features import common

MAX_DRAW = 240
MAX_CAPSULE_TEXT = 4000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _phase_block(settings: dict) -> str:
    if not settings.get("moon"):
        return ""
    phase = moon_phase_name(_utcnow())
    return (
        f'<section class="section feature-block" data-misa-feature="moon">'
        f'<h2>Moon</h2><p class="feature-text moon-phase" data-phase="{escape(phase, quote=True)}">{escape(phase)}</p>'
        "</section>"
    )


def moon_phase_name(moment: datetime) -> str:
    """Approximate lunar phase name for the given UTC moment."""
    reference = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    days = (moment.astimezone(timezone.utc) - reference).total_seconds() / 86400.0
    within = (days % 29.530588853) / 29.530588853
    if within < 0.03 or within >= 0.97:
        return "New moon"
    if within < 0.22:
        return "Waxing crescent"
    if within < 0.28:
        return "First quarter"
    if within < 0.50:
        return "Waxing gibbous"
    if within < 0.53:
        return "Full moon"
    if within < 0.72:
        return "Waning gibbous"
    if within < 0.78:
        return "Last quarter"
    return "Waning crescent"


def _reverse_block(settings: dict) -> str:
    title = str(settings.get("reverse", {}).get("title") or "").strip()[:120]
    text = str(settings.get("reverse", {}).get("text") or "").strip()
    if not title and not text:
        return ""
    title_html = escape(title) if title else "the other side"
    text_html = "<br>".join(escape(line) for line in text.splitlines()) if text else ""
    body = f'<p class="feature-text">{text_html}</p>' if text_html else ""
    return (
        f'<section class="section section-flip feature-block" data-misa-feature="reverse">'
        f"<h2>{title_html}</h2>{body}</section>"
    )


def _night_block(settings: dict) -> str:
    night = settings.get("night") if isinstance(settings.get("night"), dict) else {}
    tz = str(night.get("tz") or "").strip()
    start = int(night.get("from") or 23)
    end = int(night.get("to") or 5)
    if not tz and start == 23 and end == 5:
        return ""
    zone = escape(tz, quote=True) if tz else ""
    label = f"{start:02d}:00 to {end:02d}:00"
    return (
        f'<section class="section feature-block" data-misa-feature="night">'
        f'<h2>Night mode</h2><p class="feature-text">active {label}{f" in {zone}" if zone else ""}</p>'
        "</section>"
    )


def _draw_block(settings: dict) -> str:
    text = str(settings.get("draw") or "").strip()
    if not text:
        return ""
    text_html = "<br>".join(escape(line) for line in text.splitlines()[:12])
    return (
        f'<section class="section section-flip feature-block" data-misa-feature="draw">'
        f"<h2>Draw</h2><p class=\"feature-text draw-note\">{text_html}</p>"
        "</section>"
    )


def _capsule_block(settings: dict) -> str:
    capsule = settings.get("capsule") if isinstance(settings.get("capsule"), dict) else {}
    text = str(capsule.get("text") or "").strip()
    at = str(capsule.get("at") or "").strip()
    if not text and not at:
        return ""
    sealed = True
    if at:
        parsed = common.parse_iso_utc(at)
        if parsed:
            try:
                opens = datetime.fromisoformat(parsed.replace("Z", "+00:00"))
                sealed = opens > _utcnow()
            except ValueError:
                sealed = False
    if sealed:
        when = escape(at, quote=True) if at else ""
        return (
            f'<section class="section feature-block" data-misa-feature="capsule">'
            f'<h2>Time capsule</h2><p class="feature-text">sealed{f" until {when}" if when else ""} - opens in the future.</p>'
            "</section>"
        )
    text_html = "<br>".join(escape(line) for line in text.splitlines()) if text else ""
    return (
        f'<section class="section feature-block" data-misa-feature="capsule">'
        f"<h2>Time capsule</h2>{f'<p class=\"feature-text\">{text_html}</p>' if text_html else ''}"
        "</section>"
    )


def _archive_block(settings: dict) -> str:
    if not settings.get("archive"):
        return ""
    return (
        '<section class="section feature-block" data-misa-feature="archive">'
        "<h2>Archive</h2><p class=\"feature-text\">collected entries live here.</p>"
        "</section>"
    )


def _neighbours_block(settings: dict) -> str:
    names = [item for item in (settings.get("neighbours") or []) if isinstance(item, str) and item.strip()]
    if not names:
        return ""
    links = "".join(
        f'<a class="section-tag neighbour-chip" href="/{escape(name, quote=True)}">{escape(name)}</a>'
        for name in names[:5]
    )
    return (
        f'<section class="section feature-block" data-misa-feature="neighbours">'
        f"<h2>Neighbours</h2><div class=\"section-tags\">{links}</div>"
        "</section>"
    )


def _presence_block(settings: dict) -> str:
    if not settings.get("presence"):
        return ""
    now = _utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return (
        f'<section class="section feature-block" data-misa-feature="presence">'
        f'<h2>Presence</h2><p class="feature-text presence-now">{escape(now)}</p>'
        "</section>"
    )


def feature_blocks_html(settings: dict) -> str:
    blocks = [
        _reverse_block(settings),
        _night_block(settings),
        _draw_block(settings),
        _capsule_block(settings),
        _archive_block(settings),
        _moon_block(settings),
        _neighbours_block(settings),
        _presence_block(settings),
    ]
    rendered = "".join(block for block in blocks if block)
    return rendered


def _moon_block(settings: dict) -> str:
    return _phase_block(settings)


def has_feature_blocks(settings: dict) -> bool:
    return bool(feature_blocks_html(settings))


def stripped_secret(settings: dict) -> dict:
    """Public-safe copy of settings: never leaks secret words, hashes, urls or labels.

    The reveal is a game — nothing is shown to visitors until their submitted word
    hashes to the owner's stored wordHash server-side.
    """
    cleaned = dict(settings)
    secret = cleaned.get("secret") if isinstance(cleaned.get("secret"), dict) else {}
    has_secret = bool(secret.get("word") or secret.get("wordHash"))
    cleaned["secret"] = {
        "word": "",
        "wordHash": "",
        "url": "",
        "label": "",
        "hasSecret": has_secret,
    }
    return cleaned