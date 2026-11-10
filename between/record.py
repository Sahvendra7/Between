"""The family's tamper-evident record: every event names its actor and is chained to the one before.

Chain idea from Kitty's pot.py (chain_next), widened to full sha256. Bodies hold ids, amounts and
citations only; document text, quotes, prompts, receipts and notes are refused.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal, TypedDict

import sqlalchemy as sa

from between import db

GENESIS = "0" * 64
BODY_FORBIDDEN_KEYS = {"text", "quote", "prompt", "receipt", "note"}


class Actor(TypedDict):
    kind: Literal["parent", "system", "paypal"]
    role: str | None
    session_ref: str | None


SYSTEM: Actor = {"kind": "system", "role": None, "session_ref": None}
PAYPAL: Actor = {"kind": "paypal", "role": None, "session_ref": None}


def _forbidden(obj) -> bool:
    if isinstance(obj, dict):
        return any(k in BODY_FORBIDDEN_KEYS or _forbidden(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(_forbidden(v) for v in obj)
    return False


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _stamp(at: datetime) -> str:
    if at.tzinfo is not None:
        at = at.astimezone(timezone.utc).replace(tzinfo=None)
    return at.isoformat(timespec="microseconds")


def _hash(prev: str, type_: str, body_json: str, actor_json: str, at: datetime) -> str:
    payload = _canon({"type": type_, "body": json.loads(body_json), "actor": json.loads(actor_json), "at": _stamp(at)})
    return hashlib.sha256((prev + payload).encode()).hexdigest()


def append(conn, family_id: str, type: str, body: dict, actor: Actor, now: datetime | None = None) -> dict:
    if _forbidden(body):
        raise ValueError("event bodies must not hold document text, quotes, prompts, receipts or notes")
    at = now or datetime.now(timezone.utc)
    last = conn.execute(sa.select(db.event.c.seq, db.event.c.hash).where(db.event.c.family_id == family_id)
                        .order_by(db.event.c.seq.desc()).limit(1)).first()
    seq, prev = (last.seq + 1, last.hash) if last else (1, GENESIS)
    body_json, actor_json = _canon(body), _canon(dict(actor))
    row = {"family_id": family_id, "seq": seq, "type": type, "body_json": body_json, "actor_json": actor_json,
           "prev": prev, "hash": _hash(prev, type, body_json, actor_json, at), "at": at}
    conn.execute(sa.insert(db.event).values(**row))
    return row


def events(conn, family_id: str) -> list[dict]:
    rows = conn.execute(sa.select(db.event).where(db.event.c.family_id == family_id).order_by(db.event.c.seq)).mappings()
    return [{**dict(r), "body": json.loads(r["body_json"]), "actor": json.loads(r["actor_json"])} for r in rows]


def check(conn, family_id: str) -> int | None:
    """The first seq where the chain breaks (edited, missing or reordered), or None if intact."""
    prev, expected = GENESIS, 1
    for e in events(conn, family_id):
        if e["seq"] != expected or e["prev"] != prev or e["hash"] != _hash(prev, e["type"], e["body_json"], e["actor_json"], e["at"]):
            return e["seq"]
        prev, expected = e["hash"], expected + 1
    return None
