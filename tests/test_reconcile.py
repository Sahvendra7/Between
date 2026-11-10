import json
from pathlib import Path

import httpx
import sqlalchemy as sa

from between import db, payments as P, reconcile as R, record
from conftest import insert_expense, insert_family

FX = Path(__file__).parent / "fixtures" / "paypal"
PAYEE = "sb***@personal.example.com"  # fixtures are redacted the same way


def fx(name):
    return json.loads((FX / f"{name}.json").read_text())


def setup(conn, now, status="captured_pending_verify", capture_id="38L069926Y258024J"):
    insert_family(conn)
    conn.execute(sa.insert(db.parent).values(family_id="f1", role="A", label="Mother", display_name="Maria", paypal_email=PAYEE))
    conn.execute(sa.insert(db.parent).values(family_id="f1", role="B", label="Father", display_name="David",
                                             paypal_email="sb-b@personal.example.com"))
    insert_expense(conn)
    conn.execute(sa.insert(db.payment).values(
        id="p1", expense_id="e1", kind="share", payer_role="B", payee_role="A", amount_minor=25200,
        order_id="5H058147FB671984G", capture_id=capture_id, request_id="pay_p1",
        status="approved" if capture_id else "created", verification="unverified", fee_estimate_minor=928))


class FakePP:
    def __init__(self, *captures, order=None, error=None):
        self.captures, self.order, self.error, self.calls = list(captures), order, error, []

    def get_capture(self, cid):
        self.calls.append(("capture", cid))
        if self.error:
            raise self.error
        return self.captures.pop(0) if len(self.captures) > 1 else self.captures[0]

    def get_order(self, oid):
        self.calls.append(("order", oid))
        return self.order


def row(conn):
    return dict(conn.execute(sa.select(db.payment).where(db.payment.c.id == "p1")).mappings().one())


def test_apply_capture_sets_breakdown_and_verified(now):
    r = {"amount_minor": 25200, "expense_id": "e1", "payee_email": PAYEE, "status": "approved"}
    ch = R.apply_capture(r, fx("get_capture_completed"), now)
    assert (ch["status"], ch["verification"], ch["gross_minor"], ch["fee_minor"], ch["net_minor"]) == ("completed", "verified", 25200, 928, 24272)


def test_amount_mismatch_never_verifies(now):
    r = {"amount_minor": 25000, "expense_id": "e1", "payee_email": PAYEE, "status": "approved"}
    ch = R.apply_capture(r, fx("get_capture_completed"), now)
    assert ch.get("verification") != "verified" and ch["last_error"] == "mismatch:amount"


def test_payee_mismatch_never_verifies(now):
    r = {"amount_minor": 25200, "expense_id": "e1", "payee_email": "sb-x@personal.example.com", "status": "approved"}
    assert R.apply_capture(r, fx("get_capture_completed"), now)["last_error"] == "mismatch:payee"


def test_verify_payment_marks_paid_and_records_event(conn, now):
    setup(conn, now)
    R.verify_payment(conn, FakePP(fx("get_capture_completed")), "p1", record.SYSTEM, now)
    r = row(conn)
    assert R.counts_as_paid(r) and r["last_verified_at"] is not None
    assert [e["type"] for e in record.events(conn, "f1")] == ["payment.status_changed"]


def test_reverify_can_downgrade_completed_to_refunded(conn, now):
    setup(conn, now)
    pp = FakePP(fx("get_capture_completed"), fx("get_capture_refunded"))
    R.verify_payment(conn, pp, "p1", record.SYSTEM, now)
    R.verify_payment(conn, pp, "p1", record.SYSTEM, now)
    r = row(conn)
    assert r["status"] == "refunded" and not R.counts_as_paid(r)
    assert conn.execute(sa.select(db.expense.c.status).where(db.expense.c.id == "e1")).scalar() == "reopened"
    assert [e["type"] for e in record.events(conn, "f1")][-2:] == ["payment.status_changed", "expense.reopened"]


def test_partially_refunded_still_counts_but_reopens(conn, now):
    setup(conn, now)
    R.verify_payment(conn, FakePP(fx("get_capture_partially_refunded")), "p1", record.SYSTEM, now)
    r = row(conn)
    assert r["status"] == "partially_refunded" and R.counts_as_paid(r)
    assert conn.execute(sa.select(db.expense.c.status).where(db.expense.c.id == "e1")).scalar() == "reopened"


def test_pending_then_completed(conn, now):
    setup(conn, now)
    pp = FakePP(fx("get_capture_pending"), fx("get_capture_completed"))
    R.verify_payment(conn, pp, "p1", record.SYSTEM, now)
    assert row(conn)["status"] == "pending" and not R.counts_as_paid(row(conn))
    R.verify_payment(conn, pp, "p1", record.SYSTEM, now)
    assert row(conn)["status"] == "completed" and R.counts_as_paid(row(conn))


def test_paypal_unreachable_sets_verification_unavailable_without_downgrade(conn, now):
    setup(conn, now)
    R.verify_payment(conn, FakePP(fx("get_capture_completed")), "p1", record.SYSTEM, now)
    R.verify_payment(conn, FakePP(error=httpx.ConnectError("down")), "p1", record.SYSTEM, now)
    r = row(conn)
    assert (r["status"], r["verification"]) == ("completed", "verification_unavailable") and "network" in r["last_error"]


def test_paypal_5xx_sets_verification_unavailable(conn, now):
    setup(conn, now)
    R.verify_payment(conn, FakePP(error=P.PayPalError(503, "SERVICE_UNAVAILABLE", None, "d")), "p1", record.SYSTEM, now)
    assert row(conn)["verification"] == "verification_unavailable"


def test_unknown_capture_status_recorded_not_mapped(conn, now):
    setup(conn, now)
    weird = {**fx("get_capture_completed"), "status": "SOMETHING_NEW"}
    R.verify_payment(conn, FakePP(weird), "p1", record.SYSTEM, now)
    r = row(conn)
    assert r["status"] == "approved" and r["last_error"] == "unknown_capture_status:SOMETHING_NEW"


def test_reversal_report_needs_capture_confirmation(conn, now):
    setup(conn, now)
    R.verify_payment(conn, FakePP(fx("get_capture_completed")), "p1", record.SYSTEM, now, reversal_reported=True)
    r = row(conn)
    assert r["status"] == "completed" and r["last_error"] == "reversal_reported_unconfirmed"
    R.verify_payment(conn, FakePP(fx("get_capture_refunded")), "p1", record.SYSTEM, now, reversal_reported=True)
    assert row(conn)["status"] == "reversed"


def test_order_without_capture_is_read_from_order(conn, now):
    setup(conn, now, capture_id=None)
    order = fx("get_order_completed")
    order["purchase_units"][0]["payments"]["captures"][0]["custom_id"] = "exp_e1"
    pp = FakePP(fx("get_capture_completed"), order=order)
    R.verify_payment(conn, pp, "p1", record.SYSTEM, now)
    assert row(conn)["capture_id"] and pp.calls[0][0] == "order"
