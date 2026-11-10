import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from between import db
from conftest import insert_expense, insert_family


def pay(conn, pid, status="created", kind="share", req=None):
    conn.execute(sa.insert(db.payment).values(
        id=pid, expense_id="e1", kind=kind, payer_role="B", payee_role="A", amount_minor=25200,
        request_id=req or f"pay_{pid}", status=status, verification="unverified"))


def test_tables_exist(conn):
    assert {"family", "payment", "event", "answer"} <= set(sa.inspect(conn).get_table_names())


def test_live_payment_unique_per_expense_kind(conn):
    insert_family(conn); insert_expense(conn)
    pay(conn, "p1")
    with pytest.raises(IntegrityError):
        with conn.begin_nested():
            pay(conn, "p2")


def test_failed_payment_allows_retry(conn):
    insert_family(conn); insert_expense(conn)
    pay(conn, "p1", status="failed")
    pay(conn, "p2")


def test_duplicate_request_id_rejected(conn):
    insert_family(conn); insert_expense(conn)
    pay(conn, "p1", status="failed", req="same")
    with pytest.raises(IntegrityError):
        with conn.begin_nested():
            pay(conn, "p2", req="same")


def test_duplicate_receipt_hash_rejected(conn):
    insert_family(conn); insert_expense(conn, "e1", sha="h")
    with pytest.raises(IntegrityError):
        with conn.begin_nested():
            insert_expense(conn, "e2", sha="h")


def test_consent_used_once(conn):
    insert_family(conn); insert_expense(conn)
    row = dict(family_id="f1", requested_by="A", category="medical", max_minor=50000, given_by="B",
               given_on="2026-09-01", used_by_expense_id="e1")
    conn.execute(sa.insert(db.consent).values(id="c1", **row))
    with pytest.raises(IntegrityError):
        with conn.begin_nested():
            conn.execute(sa.insert(db.consent).values(id="c2", **row))


def test_init_db_is_idempotent(engine):
    db.init_db(engine)
