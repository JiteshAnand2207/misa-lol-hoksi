"""Feature data storage for misa.lol.

All tables created by this module carry the `misa_` prefix so they can never
collide or be merged with the production schema (profiles, users,
constellations, ...). Creation is idempotent and non-destructive: existing
tables are never dropped or altered beyond additive idempotent columns, and
the module only touches `misa_*` names.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import asyncpg

from app.db import admin_db


def _now_iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)[:40]


def _row_to_dict(row: asyncpg.Record | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "ownerId": str(row["owner_id"]),
        "q": str(row["text"]),
        "a": str(row["answer"] or ""),
        "status": str(row["status"]),
        "at": _now_iso(row["created_at"]),
    }


def hash_ip(ip: str) -> str:
    return hashlib.sha256((ip or "").encode("utf-8")).hexdigest()


async def ensure_misa_asks() -> None:
    pool = admin_db.database_pool()
    statements = (
        """
        CREATE TABLE IF NOT EXISTS misa_asks (
            id UUID PRIMARY KEY,
            owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            text VARCHAR(400) NOT NULL,
            author VARCHAR(48) NOT NULL DEFAULT '',
            status VARCHAR(16) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'published')),
            answer VARCHAR(2000) NOT NULL DEFAULT '',
            ip_hash CHAR(64) NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            answered_at TIMESTAMPTZ
        )
        """,
        "CREATE INDEX IF NOT EXISTS misa_asks_owner_idx ON misa_asks (owner_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS misa_asks_public_idx ON misa_asks (owner_id, created_at DESC) WHERE status = 'published'",
    )
    async with pool.acquire() as conn:
        async with conn.transaction():
            for statement in statements:
                await conn.execute(statement)


async def ensure_feature_tables() -> None:
    """Install every misa_* feature table. Idempotent and additive only."""
    if not admin_db.has_pool():
        return
    await ensure_misa_asks()


async def list_owner_asks(owner_id: str) -> dict[str, list[dict[str, Any]]]:
    pool = admin_db.database_pool()
    rows = await pool.fetch(
        """
        SELECT id, owner_id, text, answer, status, created_at
        FROM misa_asks
        WHERE owner_id = $1
        ORDER BY created_at DESC
        LIMIT 500
        """,
        UUID(owner_id),
    )
    waiting: list[dict[str, Any]] = []
    answered: list[dict[str, Any]] = []
    for row in rows:
        item = _row_to_dict(row)
        if item is None:
            continue
        if item["status"] == "pending":
            waiting.append(item)
        else:
            answered.append(item)
    return {"waiting": waiting, "answered": answered}


async def list_published_asks(owner_id: str, limit: int = 50) -> list[dict[str, Any]]:
    pool = admin_db.database_pool()
    rows = await pool.fetch(
        """
        SELECT id, owner_id, text, answer, status, created_at
        FROM misa_asks
        WHERE owner_id = $1 AND status = 'published'
        ORDER BY answered_at DESC NULLS LAST, created_at DESC
        LIMIT $2
        """,
        UUID(owner_id),
        max(1, min(limit, 200)),
    )
    return [item for item in (_row_to_dict(row) for row in rows) if item is not None]


async def create_ask(
    owner_id: str,
    question: str,
    *,
    author: str = "",
    ip: str = "",
) -> dict[str, Any]:
    pool = admin_db.database_pool()
    ask_id = uuid4()
    row = await pool.fetchrow(
        """
        INSERT INTO misa_asks (id, owner_id, text, author, ip_hash)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, owner_id, text, answer, status, created_at
        """,
        ask_id,
        UUID(owner_id),
        question,
        author,
        hash_ip(ip) if ip else "",
    )
    return _row_to_dict(row) or {}


async def get_ask(owner_id: str, ask_id: str) -> dict[str, Any] | None:
    pool = admin_db.database_pool()
    row = await pool.fetchrow(
        """
        SELECT id, owner_id, text, answer, status, created_at
        FROM misa_asks
        WHERE id = $1 AND owner_id = $2
        """,
        UUID(ask_id),
        UUID(owner_id),
    )
    return _row_to_dict(row)


async def answer_ask(owner_id: str, ask_id: str, answer: str) -> dict[str, Any] | None:
    pool = admin_db.database_pool()
    row = await pool.fetchrow(
        """
        UPDATE misa_asks
        SET answer = $3, status = 'published', answered_at = NOW()
        WHERE id = $1 AND owner_id = $2 AND status = 'pending'
        RETURNING id, owner_id, text, answer, status, created_at
        """,
        UUID(ask_id),
        UUID(owner_id),
        answer,
    )
    return _row_to_dict(row)


async def edit_answer(owner_id: str, ask_id: str, answer: str) -> dict[str, Any] | None:
    pool = admin_db.database_pool()
    row = await pool.fetchrow(
        """
        UPDATE misa_asks
        SET answer = $3, answered_at = NOW()
        WHERE id = $1 AND owner_id = $2 AND status = 'published'
        RETURNING id, owner_id, text, answer, status, created_at
        """,
        UUID(ask_id),
        UUID(owner_id),
        answer,
    )
    return _row_to_dict(row)


async def delete_ask(owner_id: str, ask_id: str) -> bool:
    pool = admin_db.database_pool()
    result = await pool.execute(
        "DELETE FROM misa_asks WHERE id = $1 AND owner_id = $2",
        UUID(ask_id),
        UUID(owner_id),
    )
    return result == "DELETE 1"