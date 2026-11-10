"""PayPal's view of a payment, read back and reconciled (spec r2 §8).

`status` is the money state and only a GET from PayPal changes it. `verification` says whether
Between has confirmed it. Re-verifying may change an already verified payment (a refund made by the
receiving parent in PayPal). If PayPal can't be reached, nothing is downgraded.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import httpx
import sqlalchemy as sa

from between import db, record
from between.payments import PayPalError

CAPTURE_TO_STATUS = {"COMPLETED": "completed", "PENDING": "pending", "PARTIALLY_REFUNDED": "partially_refunded",
                     "REFUNDED": "refunded", "DECLINED": "declined", "FAILED": "failed"}
REOPENS = {"refunded", "partially_refunded", "reversed"}


def _cents(money: dict | None) -> int | None:
    return None if not money else int(Decimal(money["value"]) * 100)


def expected_custom_id(row: dict) -> str:
    return f"exp_{row['expense_id']}" if row.get("kind", "share") == "share" else f"corr_{row['id']}"


def apply_capture(row: dict, capture: dict, now: datetime) -> dict:
    """Changed columns for a payment row given PayPal's capture. Mismatches never verify."""
    raw = capture.get("status")
    if raw not in CAPTURE_TO_STATUS:
        return {"paypal_status": raw, "last_error": f"unknown_capture_status:{raw}"}
    payee = ((capture.get("payee") or {}).get("email_address") or "").lower()
    if _cents(capture.get("amount")) != row["amount_minor"]:
        return {"paypal_status": raw, "last_error": "mismatch:amount"}
    if capture.get("custom_id") != row.get("custom_id", expected_custom_id(row)):
        return {"paypal_status": raw, "last_error": "mismatch:custom_id"}
    if payee and payee != (row.get("payee_email") or "").lower():
        return {"paypal_status": raw, "last_error": "mismatch:payee"}
    b = capture.get("seller_receivable_breakdown") or {}
    return {"status": CAPTURE_TO_STATUS[raw], "paypal_status": raw, "capture_id": capture.get("id"),
            "gross_minor": _cents(b.get("gross_amount")) or _cents(capture.get("amount")),
            "fee_minor": _cents(b.get("paypal_fee")), "net_minor": _cents(b.get("net_amount")),
            "verification": "verified", "last_verified_at": now, "last_error": None}


def counts_as_paid(row: dict) -> bool:
    return row["status"] in {"completed", "partially_refunded"} and row["verification"] == "verified"


def _load(conn, payment_id) -> dict:
    p, e, par = db.payment, db.expense, db.parent
    q = (sa.select(p, e.c.family_id, par.c.paypal_email.label("payee_email"))
         .join(e, e.c.id == p.c.expense_id)
         .join(par, sa.and_(par.c.family_id == e.c.family_id, par.c.role == p.c.payee_role))
         .where(p.c.id == payment_id))
    return dict(conn.execute(q).mappings().one())


def verify_payment(conn, pp, payment_id: str, actor, now: datetime, reversal_reported: bool = False) -> dict:
    row = _load(conn, payment_id)
    changes: dict
    try:
        if row["capture_id"]:
            changes = apply_capture(row, pp.get_capture(row["capture_id"]), now)
        else:
            order = pp.get_order(row["order_id"])
            caps = ((order.get("purchase_units") or [{}])[0].get("payments") or {}).get("captures") or []
            if caps:
                changes = apply_capture(row, caps[0], now)
            elif order.get("status") == "APPROVED":
                changes = {"status": "approved"}
            elif order.get("status") == "VOIDED":
                changes = {"status": "cancelled"}
            else:
                changes = {}
        if reversal_reported and "status" in changes:
            if changes.get("paypal_status") == "COMPLETED":
                changes["last_error"] = "reversal_reported_unconfirmed"
            else:
                changes["status"] = "reversed"
    except (httpx.HTTPError, PayPalError) as exc:
        if isinstance(exc, PayPalError) and exc.status < 500:
            changes = {"last_error": f"paypal:{exc.status}:{exc.name}"}
        else:
            changes = {"verification": "verification_unavailable", "last_error": f"network:{type(exc).__name__}"}
    if changes:
        conn.execute(sa.update(db.payment).where(db.payment.c.id == payment_id).values(**changes))
    new_status = changes.get("status", row["status"])
    if new_status != row["status"]:
        record.append(conn, row["family_id"], "payment.status_changed",
                      {"payment_id": payment_id, "from": row["status"], "to": new_status,
                       "capture_id": changes.get("capture_id") or row["capture_id"]}, actor, now=now)
        if new_status in REOPENS and row["status"] not in REOPENS:
            conn.execute(sa.update(db.expense).where(db.expense.c.id == row["expense_id"]).values(status="reopened"))
            record.append(conn, row["family_id"], "expense.reopened",
                          {"expense_id": row["expense_id"], "payment_id": payment_id, "because": new_status}, actor, now=now)
    return _load(conn, payment_id)


def complete_if_approved(conn, pp, payment_id: str, actor, now: datetime, reversal_reported: bool = False) -> dict:
    """Finish a checkout the payer confirmed in Between and approved on PayPal but never returned from
    (closed tab, other browser). Only live, uncaptured payments; the capture request id is the same one
    the return page uses, so PayPal can't charge twice. Then verify as usual."""
    from between.payments import ALREADY_CAPTURED
    row = _load(conn, payment_id)
    if row["order_id"] and not row["capture_id"] and row["status"] in ("created", "approved"):
        try:
            if pp.get_order(row["order_id"]).get("status") == "APPROVED":
                captured = pp.capture_order(row["order_id"], f"pay_{payment_id}_capture")
                caps = ((captured.get("purchase_units") or [{}])[0].get("payments") or {}).get("captures") or []
                if caps:
                    conn.execute(sa.update(db.payment).where(db.payment.c.id == payment_id).values(capture_id=caps[0]["id"]))
        except PayPalError as exc:
            if exc.issue != ALREADY_CAPTURED:
                conn.execute(sa.update(db.payment).where(db.payment.c.id == payment_id)
                             .values(last_error=f"capture:{exc.issue or exc.name}"))
        except httpx.HTTPError:
            pass  # verify_payment below records the unavailability
    return verify_payment(conn, pp, payment_id, actor, now, reversal_reported=reversal_reported)
