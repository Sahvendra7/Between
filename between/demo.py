"""Synthetic-only controls for the hosted demo (spec r2 §9), and (Task 12) the idempotent seed."""
from __future__ import annotations

import re

from between.config import Settings

SYNTHETIC_MARKER = "SYNTHETIC DOCUMENT FOR SOFTWARE TESTING"
SANDBOX_DOMAINS = ("@personal.example.com", "@business.example.com")
MAX_AGREEMENT_CHARS = 60_000
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
UPLOAD_TYPES = {"image/png", "image/jpeg", "application/pdf", "text/plain"}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MESSAGES = {
    "not_synthetic": "This demo only accepts synthetic agreements: the text must contain the line "
                     f"\"{SYNTHETIC_MARKER}\". Please use one of the sample agreements.",
    "too_long": "This agreement is too long for the demo (60,000 characters at most).",
    "empty": "There's no text to read.",
    "not_sandbox_email": "Use a PayPal sandbox account email (ending in @personal.example.com or @business.example.com).",
    "bad_email": "That doesn't look like an email address.",
    "bad_type": "Upload a PNG, JPEG or PDF file.",
    "too_big": "That file is larger than 2 MB.",
}


class DemoGuard(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
        self.message = MESSAGES.get(code, code)


def check_agreement_text(text: str, settings: Settings) -> None:
    if not (text or "").strip():
        raise DemoGuard("empty")
    if len(text) > MAX_AGREEMENT_CHARS:
        raise DemoGuard("too_long")
    if settings.demo_mode and SYNTHETIC_MARKER not in text:
        raise DemoGuard("not_synthetic")


def check_paypal_email(email: str, settings: Settings) -> None:
    email = (email or "").strip().lower()
    if not EMAIL.match(email):
        raise DemoGuard("bad_email")
    if settings.demo_mode and not email.endswith(SANDBOX_DOMAINS):
        raise DemoGuard("not_sandbox_email")


def check_upload(content_type: str | None, size: int, settings: Settings) -> None:
    if (content_type or "") not in UPLOAD_TYPES:
        raise DemoGuard("bad_type")
    if size > MAX_UPLOAD_BYTES:
        raise DemoGuard("too_big")


# ---- seeding (Task 12): idempotent and non-destructive ---------------------------------------
import json  # noqa: E402
import uuid  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import sqlalchemy as sa  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
SEED_ACTOR = {"kind": "system", "role": None, "session_ref": "demo-seed"}


def _sample_ruleset():
    from between import validate as V
    text = (SAMPLES / "agreements" / "plan1_rivera_okafor.txt").read_text()
    raw = json.loads((SAMPLES / "plan1_approved_rules.json").read_text())
    return text, raw["parties"], V.validate(raw, text, raw["parties"])


def _make_family(conn, settings, now, demo_key, approve: bool) -> str:
    from between import db, record, ruleset as RS
    text, parties, validated = _sample_ruleset()
    fid = uuid.uuid4().hex[:12]
    conn.execute(sa.insert(db.family).values(id=fid, created_at=now, currency="USD", demo_key=demo_key))
    conn.execute(sa.insert(db.parent).values(family_id=fid, role="A", label=parties["A"], display_name="Maria (demo)",
                                             paypal_email=settings.demo_parent_a_email or None))
    conn.execute(sa.insert(db.parent).values(family_id=fid, role="B", label=parties["B"], display_name="David (demo)",
                                             paypal_email=settings.demo_parent_b_email or None))
    record.append(conn, fid, "family.created", {"family_id": fid, "labels": parties, "demo": True}, SEED_ACTOR, now=now)
    aid = uuid.uuid4().hex[:12]
    import hashlib
    conn.execute(sa.insert(db.agreement).values(id=aid, family_id=fid, sha256=hashlib.sha256(text.encode()).hexdigest(),
                                                text=text, uploaded_by="A", uploaded_at=now))
    v = RS.create_version(conn, fid, aid, validated, parties, SEED_ACTOR, now=now)
    from between.schedule import last_changeover
    from between.web.routes_calendar import store_schedule
    sched = json.loads((SAMPLES / "plan1_schedule.json").read_text())
    store_schedule(conn, fid, aid, sched, anchor=last_changeover(sched, now.replace(tzinfo=None)).isoformat(), first_parent="A")
    if approve:
        for role in ("A", "B"):
            RS.approve(conn, v["id"], role, v["hash"], SEED_ACTOR, now=now)
    return fid


def seed(conn, settings: Settings, now: datetime | None = None) -> str:
    """The base demo family exists after this. Never updates or deletes anything."""
    from between import db
    now = now or datetime.now(timezone.utc)
    found = conn.execute(sa.select(db.family.c.id).where(db.family.c.demo_key == "demo-1")).scalar()
    return found or _make_family(conn, settings, now, "demo-1", approve=True)


def new_demo_family(conn, settings: Settings, now: datetime | None = None) -> tuple[str, str, str]:
    """A fresh family per visitor, from the samples, rules not yet approved: (family_id, invite_A, invite_B)."""
    from between import access
    now = now or datetime.now(timezone.utc)
    fid = _make_family(conn, settings, now, f"visitor-{uuid.uuid4().hex[:12]}", approve=False)
    return fid, access.create_invite(conn, fid, "A", now), access.create_invite(conn, fid, "B", now)


def is_visitor_family(conn, family_id: str) -> bool:
    from between import db
    key = conn.execute(sa.select(db.family.c.demo_key).where(db.family.c.id == family_id)).scalar()
    return bool(key and key.startswith("visitor-"))
