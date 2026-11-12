"""Schema (spec r2 §10) for SQLite locally and Postgres hosted. create_all only: never drops."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Boolean, Column, DateTime, Index, Integer, MetaData, String, Table, Text, UniqueConstraint

metadata = MetaData()
TS = DateTime(timezone=True)

family = Table(
    "family", metadata,
    Column("id", String, primary_key=True),
    Column("created_at", TS, nullable=False),
    Column("currency", String, nullable=False, default="USD"),
    Column("demo_key", String, unique=True, nullable=True),
)

parent = Table(
    "parent", metadata,
    Column("family_id", String, sa.ForeignKey("family.id"), primary_key=True),
    Column("role", String, primary_key=True),
    Column("label", String, nullable=False),
    Column("display_name", String, nullable=False),
    Column("paypal_email", String, nullable=True),
)

invite = Table(
    "invite", metadata,
    Column("token_hash", String, primary_key=True),
    Column("family_id", String, sa.ForeignKey("family.id"), nullable=False),
    Column("role", String, nullable=False),
    Column("expires_at", TS, nullable=False),
    Column("used_at", TS),
    Column("revoked_at", TS),
)

session = Table(
    "session", metadata,
    Column("id_hash", String, primary_key=True),
    Column("family_id", String, sa.ForeignKey("family.id"), nullable=False),
    Column("role", String, nullable=False),
    Column("csrf", String, nullable=False),
    Column("created_at", TS, nullable=False),
    Column("expires_at", TS, nullable=False),
    Column("revoked_at", TS),
)

agreement = Table(
    "agreement", metadata,
    Column("id", String, primary_key=True),
    Column("family_id", String, sa.ForeignKey("family.id"), nullable=False),
    Column("sha256", String, nullable=False),
    Column("text", Text, nullable=False),
    Column("uploaded_by", String, nullable=False),
    Column("uploaded_at", TS, nullable=False),
)

ruleset = Table(
    "ruleset", metadata,
    Column("id", String, primary_key=True),
    Column("family_id", String, sa.ForeignKey("family.id"), nullable=False),
    Column("agreement_id", String, sa.ForeignKey("agreement.id"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("json", Text, nullable=False),
    Column("hash", String, nullable=False),
    Column("created_at", TS, nullable=False),
    UniqueConstraint("family_id", "version"),
)

approval = Table(
    "approval", metadata,
    Column("ruleset_id", String, sa.ForeignKey("ruleset.id"), primary_key=True),
    Column("role", String, primary_key=True),
    Column("hash", String, nullable=False),
    Column("at", TS, nullable=False),
)

answer = Table(
    "answer", metadata,
    Column("ruleset_id", String, sa.ForeignKey("ruleset.id"), primary_key=True),
    Column("question_id", String, primary_key=True),
    Column("role", String, primary_key=True),
    Column("choice", String, nullable=False),
    Column("value", String),
    Column("at", TS, nullable=False),
)

expense = Table(
    "expense", metadata,
    Column("id", String, primary_key=True),
    Column("family_id", String, sa.ForeignKey("family.id"), nullable=False),
    Column("paid_by", String, nullable=False),
    Column("category", String, nullable=False),
    Column("amount_minor", Integer, nullable=False),
    Column("incurred_on", String, nullable=False),
    Column("requested_on", String, nullable=False),
    Column("receipt_sha256", String),
    Column("emergency", Boolean, nullable=False, default=False),
    Column("status", String, nullable=False),
    UniqueConstraint("family_id", "receipt_sha256"),
)

consent = Table(
    "consent", metadata,
    Column("id", String, primary_key=True),
    Column("family_id", String, sa.ForeignKey("family.id"), nullable=False),
    Column("requested_by", String, nullable=False),
    Column("category", String, nullable=False),
    Column("max_minor", Integer, nullable=False),
    Column("note", Text),
    Column("given_by", String),
    Column("given_on", String),
    Column("used_by_expense_id", String, unique=True),
)

decision = Table(
    "decision", metadata,
    Column("expense_id", String, sa.ForeignKey("expense.id"), primary_key=True),
    Column("ruleset_hash", String, nullable=False),
    Column("json", Text, nullable=False),
    Column("hash", String, nullable=False),
    Column("at", TS, nullable=False),
)

payment = Table(
    "payment", metadata,
    Column("id", String, primary_key=True),
    Column("expense_id", String, sa.ForeignKey("expense.id"), nullable=False),
    Column("kind", String, nullable=False),
    Column("payer_role", String, nullable=False),
    Column("payee_role", String, nullable=False),
    Column("amount_minor", Integer, nullable=False),
    Column("order_id", String),
    Column("capture_id", String),
    Column("request_id", String, unique=True, nullable=False),
    Column("status", String, nullable=False),
    Column("verification", String, nullable=False, default="unverified"),
    Column("paypal_status", String),
    Column("gross_minor", Integer),
    Column("fee_minor", Integer),
    Column("net_minor", Integer),
    Column("fee_estimate_minor", Integer),
    Column("last_verified_at", TS),
    Column("last_error", String),
)
_LIVE = sa.text("status NOT IN ('failed','declined','cancelled')")
Index("ix_payment_live", payment.c.expense_id, payment.c.kind, unique=True,
      sqlite_where=_LIVE, postgresql_where=_LIVE)

schedule = Table(
    "schedule", metadata,
    Column("family_id", String, sa.ForeignKey("family.id"), primary_key=True),
    Column("agreement_id", String, sa.ForeignKey("agreement.id"), nullable=False),
    Column("json", Text, nullable=False),
    Column("anchor_date", String),
    Column("first_parent", String),
    Column("set_by", String),
    Column("at", TS, nullable=False),
)

# Demo mode only: the AI's raw reading of an identical synthetic agreement, reused so repeated sample
# uploads don't spend the free-plan model quota. Output is still validated and approved like any other.
ai_cache = Table(
    "ai_cache", metadata,
    Column("key", String, primary_key=True),
    Column("json", Text, nullable=False),
    Column("at", TS, nullable=False),
)

webhook_event = Table(
    "webhook_event", metadata,
    Column("id", String, primary_key=True),
    Column("type", String, nullable=False),
    Column("resource_id", String),
    Column("verified", Boolean, nullable=False),
    Column("received_at", TS, nullable=False),
)

event = Table(
    "event", metadata,
    Column("family_id", String, primary_key=True),
    Column("seq", Integer, primary_key=True),
    Column("type", String, nullable=False),
    Column("body_json", Text, nullable=False),
    Column("actor_json", Text, nullable=False),
    Column("prev", String, nullable=False),
    Column("hash", String, nullable=False),
    Column("at", TS, nullable=False),
)


def make_engine(url: str) -> sa.Engine:
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = sa.pool.StaticPool  # one shared in-memory DB across connections
        eng = sa.create_engine(url, **kwargs)

        @sa.event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return eng
    return sa.create_engine(url, pool_pre_ping=True)


def init_db(engine: sa.Engine) -> None:
    metadata.create_all(engine)
