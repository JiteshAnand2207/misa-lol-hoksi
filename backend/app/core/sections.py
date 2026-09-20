import re
from typing import Any

LRC = re.compile(r"^\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]\s*(.*)$")
MAX_LYRIC_LINES = 200


def parse_lyrics(body: str) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for raw in str(body or "").splitlines():
        text = raw.strip()
        if not text:
            continue
        match = LRC.match(text)
        if match:
            minutes, seconds, frac, lyric = match.groups()
            stamp = int(minutes) * 60 + int(seconds) + int((frac or "0").ljust(3, "0")[:3]) / 1000
            lines.append({"t": stamp, "text": (lyric or "").strip()[:200]})
        else:
            lines.append({"t": None, "text": text[:200]})
        if len(lines) >= MAX_LYRIC_LINES:
            break
    return lines


def section_has_content(item: dict[str, Any]) -> bool:
    kind = str(item.get("type") or "")
    if kind == "skills":
        return bool(item.get("tags"))
    if kind == "project":
        cover = item.get("cover") if isinstance(item.get("cover"), dict) else {}
        return bool(item.get("title") or item.get("body") or item.get("href") or cover.get("url"))
    return bool(str(item.get("body") or "").strip() or str(item.get("title") or "").strip())
