"""Who may act as which parent. Adapted from Kitty's access.py (single-use invite → session).

Only hashes are stored. An invite opens once, expires after 72 hours, and re-issuing it revokes
the earlier invite and every session that role had, so a forwarded or stale link opens nothing.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from between import db
from between.config import Settings

INVITE_TTL = timedelta(hours=72)
SESSION_TTL = timedelta(days=14)
COOKIE_NAME = "between_session"


class AccessError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Session:
    family_id: str
    role: str
    csrf: str
    ref: str  # first 8 hex of the session hash: names the actor in the record without exposing it


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(t: datetime | None) -> datetime | None:
    return t.replace(tzinfo=timezone.utc) if t is not None and t.tzinfo is None else t  # SQLite drops tzinfo


def create_invite(conn, family_id: str, role: str, now: datetime) -> str:
    live = sa.and_(db.invite.c.family_id == family_id, db.invite.c.role == role,
                   db.invite.c.used_at.is_(None), db.invite.c.revoked_at.is_(None))
    conn.execute(sa.update(db.invite).where(live).values(revoked_at=now))
    conn.execute(sa.update(db.session).where(db.session.c.family_id == family_id, db.session.c.role == role,
                                             db.session.c.revoked_at.is_(None)).values(revoked_at=now))
    token = secrets.token_urlsafe(32)
    conn.execute(sa.insert(db.invite).values(token_hash=_hash(token), family_id=family_id, role=role,
                                             expires_at=now + INVITE_TTL))
    return token


def create_session(conn, family_id: str, role: str, now: datetime) -> str:
    raw = secrets.token_urlsafe(32)
    conn.execute(sa.insert(db.session).values(id_hash=_hash(raw), family_id=family_id, role=role,
                                              csrf=secrets.token_urlsafe(24), created_at=now, expires_at=now + SESSION_TTL))
    return raw


def redeem_invite(conn, token: str, now: datetime) -> str:
    row = conn.execute(sa.select(db.invite).where(db.invite.c.token_hash == _hash(token or ""))).mappings().first()
    if row is None:
        raise AccessError("unknown")
    if row["revoked_at"] is not None:
        raise AccessError("revoked")
    if row["used_at"] is not None:
        raise AccessError("used")
    if now > _aware(row["expires_at"]):
        raise AccessError("expired")
    conn.execute(sa.update(db.invite).where(db.invite.c.token_hash == row["token_hash"]).values(used_at=now))
    return create_session(conn, row["family_id"], row["role"], now)


def session_for(conn, raw_session_id: str | None, now: datetime) -> Session | None:
    if not raw_session_id:
        return None
    h = _hash(raw_session_id)
    row = conn.execute(sa.select(db.session).where(db.session.c.id_hash == h)).mappings().first()
    if row is None or row["revoked_at"] is not None or now > _aware(row["expires_at"]):
        return None
    return Session(row["family_id"], row["role"], row["csrf"], h[:8])


def check_csrf(session: Session, token: str | None) -> bool:
    return bool(token) and hmac.compare_digest(session.csrf, token)


def cookie_kwargs(settings: Settings) -> dict:
    return {"httponly": True, "samesite": "lax", "secure": settings.secure_cookies,
            "max_age": int(SESSION_TTL.total_seconds()), "path": "/"}
