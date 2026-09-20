"""Validation of the 13 feature settings stored in a profile's settings.

Feature keys live in the profile `settings` blob alongside pre-existing keys
(vigil, since, replay, remember, ...) which are left untouched. Values that
fail validation fall back to a safe feature default -- they never raise, so
existing profiles can never start erroring.
"""

import hashlib
from typing import Any

from app.features import common

NEIGHBOUR_RE = __import__("re").compile(r"^[a-z0-9_-]{2,24}$")
USERNAME_RE = common.plain_text  # reuse trimming for labels


def _neighbours(value: Any) -> list[str]:
    raw = value if isinstance(value, (list, tuple)) else []
    names: list[str] = []
    for item in raw:
        name = common.plain_text(item, 24).lower()
        if NEIGHBOUR_RE.match(name) and name not in names:
            names.append(name)
        if len(names) >= 5:
            break
    return names


def _options(value: Any) -> list[str]:
    raw = value if isinstance(value, (list, tuple)) else []
    options: list[str] = []
    for item in raw:
        option = common.plain_text(item, 80)
        if option and option not in options:
            options.append(option)
        if len(options) >= 4:
            break
    if len(options) < 2:
        return []
    return options


def sanitize_asks(value: Any) -> bool:
    return common.strict_bool(value, False)


def sanitize_reverse(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"title": "", "text": ""}
    return {
        "title": common.plain_text(value.get("title"), 120),
        "text": common.multiline(value.get("text"), 2000),
    }


def sanitize_night(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"tz": "", "from": 23, "to": 5}
    tz = common.parse_tz(value.get("tz"))
    return {
        "tz": tz,
        "from": common.clamp_int(value.get("from"), 23, 0, 23),
        "to": common.clamp_int(value.get("to"), 5, 0, 23),
    }


def sanitize_draw(value: Any) -> str:
    return common.plain_text(value, 240)


def sanitize_capsule(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"text": "", "at": ""}
    return {
        "text": common.multiline(value.get("text"), 4000),
        "at": common.parse_iso_utc(value.get("at")),
    }


def sanitize_archive(value: Any) -> bool:
    return common.strict_bool(value, False)


def sanitize_moon(value: Any) -> bool:
    return common.strict_bool(value, False)


def sanitize_guestbook(value: Any) -> bool:
    return common.strict_bool(value, False)


def sanitize_neighbours(value: Any) -> list[str]:
    return _neighbours(value)


def sanitize_presence(value: Any) -> bool:
    return common.strict_bool(value, False)


def sanitize_secret(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"word": "", "wordHash": "", "url": "", "label": ""}

    url = common.plain_text(value.get("url"), 500)
    if not common.is_http_url(url):
        url = ""

    word = common.plain_text(value.get("word"), 64)
    word_hash = hashlib.sha256(word.encode("utf-8")).hexdigest() if word else ""

    return {
        "word": word,
        "wordHash": word_hash,
        "url": url,
        "label": common.plain_text(value.get("label"), 80),
    }


def sanitize_doodles(value: Any) -> bool:
    return common.strict_bool(value, False)


def sanitize_tally(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not value.get("q"):
        return {"q": "", "options": []}
    q = common.plain_text(value.get("q"), 200)
    options = _options(value.get("options"))
    if not q or not options:
        return {"q": "", "options": []}
    return {"q": q, "options": options}


SANITIZERS = {
    "asks": sanitize_asks,
    "reverse": sanitize_reverse,
    "night": sanitize_night,
    "draw": sanitize_draw,
    "capsule": sanitize_capsule,
    "archive": sanitize_archive,
    "moon": sanitize_moon,
    "guestbook": sanitize_guestbook,
    "neighbours": sanitize_neighbours,
    "presence": sanitize_presence,
    "secret": sanitize_secret,
    "doodles": sanitize_doodles,
    "tally": sanitize_tally,
}


def defaults() -> dict[str, Any]:
    return {key: sanitizer(None) for key, sanitizer in SANITIZERS.items()}


def sanitize_feature(key: str, value: Any) -> Any:
    sanitizer = SANITIZERS.get(key)
    if sanitizer is None:
        return value
    return sanitizer(value)


def sanitize_all(settings: dict) -> dict:
    """Return a new settings dict with every feature key validated (defaults
    filled in when absent). Non-feature keys are passed through unchanged."""
    cleaned = dict(settings)
    for key in SANITIZERS:
        cleaned[key] = sanitize_feature(key, cleaned.get(key))
    return cleaned