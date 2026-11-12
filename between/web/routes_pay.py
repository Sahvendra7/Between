"""Pay a share: the payer confirms in Between, approves on PayPal (sandbox checkout to the other
parent's own account), Between captures and then verifies with PayPal before calling it paid."""
from __future__ import annotations

import json
import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError

from between import db, record
from between.money import fee_estimate
from between.payments import ALREADY_CAPTURED, PayPalError
from between.reconcile import counts_as_paid, verify_payment
from between.web.deps import actor, checked_form, get_conn, now, render, require_family
from between.web.routes_expenses import _expense, citations, live_payment
from between.web.routes_family import labels, parents

router = APIRouter()


def _decision(conn, eid):
    row = conn.execute(sa.select(db.decision).where(db.decision.c.expense_id == eid)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404)
    return dict(row), json.loads(row["json"])


def _pp(request):
    pp = request.app.state.pp
    if pp is None:
        raise HTTPException(status_code=503, detail="PayPal sandbox isn't configured on this server.")
    return pp


@router.get("/f/{fid}/expenses/{eid}/pay")
def pay_confirm(request: Request, fid: str, eid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    e = _expense(conn, fid, eid)
    drow, d = _decision(conn, eid)
    if d.get("status") != "payable" or s.role != d.get("owed_by"):
        raise HTTPException(status_code=403, detail="Only the parent who owes this can pay it.")
    names, people = labels(conn, fid), parents(conn, fid)
    return render(request, "pay_confirm.html", s=s, fid=fid, e=e, d=d, names=names, payee=people[d["owed_to"]],
                  cites=citations(conn, drow["ruleset_hash"], d, names, fid), fee=fee_estimate(d["amount_minor"]),
                  decision_hash=drow["hash"])


@router.post("/f/{fid}/expenses/{eid}/pay")
async def pay_start(request: Request, fid: str, eid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    form = await checked_form(request, s)
    e = _expense(conn, fid, eid)
    drow, d = _decision(conn, eid)
    if d.get("status") != "payable" or s.role != d.get("owed_by"):
        raise HTTPException(status_code=403, detail="Only the parent who owes this can pay it.")
    if form.get("confirm") != "yes":
        raise HTTPException(status_code=400, detail="Confirm the payment first.")
    if form.get("decision_hash") != drow["hash"] or e["status"] == "reopened":
        raise HTTPException(status_code=409, detail="This expense changed since you opened the page. Reload and check it again.")
    pp, settings, t = _pp(request), request.app.state.settings, now()
    live = live_payment(conn, eid, "share")
    if live and (counts_as_paid(live) or live["capture_id"] or live["status"] == "outside"):
        return RedirectResponse(f"/f/{fid}/expenses/{eid}", status_code=303)
    if live is None:
        pid = uuid.uuid4().hex[:12]
        try:
            with conn.begin_nested():
                conn.execute(sa.insert(db.payment).values(
                    id=pid, expense_id=eid, kind="share", payer_role=s.role, payee_role=d["owed_to"], amount_minor=d["amount_minor"],
                    request_id=f"pay_{pid}", status="created", verification="unverified", fee_estimate_minor=fee_estimate(d["amount_minor"])))
            record.append(conn, fid, "payment.created", {"payment_id": pid, "expense_id": eid, "amount_minor": d["amount_minor"],
                                                         "payer": s.role, "payee": d["owed_to"], "decision_hash": drow["hash"]}, actor(s), now=t)
        except IntegrityError:
            pass
        live = live_payment(conn, eid, "share")
    pid = live["id"]
    payee_email = parents(conn, fid)[live["payee_role"]]["paypal_email"]
    try:
        order = pp.create_order(live["amount_minor"], payee_email, f"exp_{eid}", f"pay_{pid}",
                                f"{settings.base_url}/pay/return?p={pid}", f"{settings.base_url}/pay/cancel?p={pid}", f"pay_{pid}_create")
    except PayPalError as err:
        conn.execute(sa.update(db.payment).where(db.payment.c.id == pid).values(status="failed", last_error=f"create:{err.issue or err.name}"))
        return render(request, "pay_result.html", 502, s=s, fid=fid, e=e, payment=None,
                      error="PayPal couldn't start this checkout. Nothing was charged. Try again in a minute.")
    if live["order_id"] != order["id"]:
        conn.execute(sa.update(db.payment).where(db.payment.c.id == pid).values(order_id=order["id"]))
        record.append(conn, fid, "payment.order_created", {"payment_id": pid, "order_id": order["id"]}, actor(s), now=t)
    return RedirectResponse(order["approve_url"], status_code=303)


def _due_correction(request, conn, fid, eid):
    s = require_family(request, conn, fid)
    e = _expense(conn, fid, eid)
    corr = live_payment(conn, eid, "correction")
    if corr is None or s.role != corr["payer_role"]:
        raise HTTPException(status_code=403, detail="Only the parent who received too much can return the difference.")
    return s, e, corr


@router.get("/f/{fid}/expenses/{eid}/return")
def return_confirm(request: Request, fid: str, eid: str, conn=Depends(get_conn)):
    s, e, corr = _due_correction(request, conn, fid, eid)
    if counts_as_paid(corr):
        return RedirectResponse(f"/f/{fid}/expenses/{eid}", status_code=303)
    return render(request, "return_confirm.html", s=s, fid=fid, e=e, corr=corr, names=labels(conn, fid),
                  payee=parents(conn, fid)[corr["payee_role"]], fee=fee_estimate(corr["amount_minor"]))


@router.post("/f/{fid}/expenses/{eid}/return")
async def return_start(request: Request, fid: str, eid: str, conn=Depends(get_conn)):
    """Same checkout as a share, in reverse: the parent who received too much pays the difference back."""
    s, e, corr = _due_correction(request, conn, fid, eid)
    form = await checked_form(request, s)
    if form.get("confirm") != "yes":
        raise HTTPException(status_code=400, detail="Confirm the return first.")
    if counts_as_paid(corr) or corr["capture_id"]:
        return RedirectResponse(f"/f/{fid}/expenses/{eid}", status_code=303)
    pp, settings, t, pid = _pp(request), request.app.state.settings, now(), corr["id"]
    payee_email = parents(conn, fid)[corr["payee_role"]]["paypal_email"]
    try:
        order = pp.create_order(corr["amount_minor"], payee_email, f"corr_{pid}", f"pay_{pid}",
                                f"{settings.base_url}/pay/return?p={pid}", f"{settings.base_url}/pay/cancel?p={pid}", f"pay_{pid}_create")
    except PayPalError as err:
        conn.execute(sa.update(db.payment).where(db.payment.c.id == pid).values(last_error=f"create:{err.issue or err.name}"))
        return render(request, "pay_result.html", 502, s=s, fid=fid, e=e, payment=None,
                      error="PayPal couldn't start this checkout. Nothing was charged. Try again in a minute.")
    if corr["order_id"] != order["id"]:
        conn.execute(sa.update(db.payment).where(db.payment.c.id == pid).values(order_id=order["id"], status="created"))
        record.append(conn, fid, "payment.order_created", {"payment_id": pid, "order_id": order["id"]}, actor(s), now=t)
    return RedirectResponse(order["approve_url"], status_code=303)


def _payment_for(request, conn, pid):
    row = conn.execute(sa.select(db.payment, db.expense.c.family_id).join(db.expense, db.expense.c.id == db.payment.c.expense_id)
                       .where(db.payment.c.id == pid)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404)
    from between.web.deps import current_session
    s = current_session(request, conn)
    if s is None or s.family_id != row["family_id"] or s.role != row["payer_role"]:
        raise HTTPException(status_code=403, detail="Not your family. If you just approved a payment in PayPal, open Between "
                            "in the browser you started from: it finishes the payment once PayPal confirms it.")
    return s, dict(row)


@router.get("/pay/return")
def pay_return(request: Request, p: str, conn=Depends(get_conn)):
    s, row = _payment_for(request, conn, p)
    fid, e = row["family_id"], _expense(conn, row["family_id"], row["expense_id"])
    if row["status"] == "cancelled":
        return RedirectResponse(f"/f/{fid}/expenses/{e['id']}", status_code=303)
    pp, t = _pp(request), now()
    try:
        captured = pp.capture_order(row["order_id"], f"pay_{p}_capture")
        caps = (captured.get("purchase_units") or [{}])[0].get("payments", {}).get("captures") or []
        if caps:
            conn.execute(sa.update(db.payment).where(db.payment.c.id == p).values(capture_id=caps[0]["id"]))
    except PayPalError as err:
        if err.issue != ALREADY_CAPTURED:
            conn.execute(sa.update(db.payment).where(db.payment.c.id == p).values(last_error=f"capture:{err.issue or err.name}"))
            msg = ("PayPal declined that payment method. Nothing was charged; try again with another one."
                   if err.issue == "INSTRUMENT_DECLINED" else "PayPal didn't complete the payment. Nothing is marked as paid.")
            return render(request, "pay_result.html", 502, s=s, fid=fid, e=e, payment=None, error=msg)
    payment = verify_payment(conn, pp, p, actor(s), t)
    return render(request, "pay_result.html", s=s, fid=fid, e=e, payment=payment, paid=counts_as_paid(payment),
                  names=labels(conn, fid))


@router.get("/pay/cancel")
def pay_cancel(request: Request, p: str, conn=Depends(get_conn)):
    s, row = _payment_for(request, conn, p)
    if row["status"] in ("created", "approved") and not row["capture_id"]:
        # a correction stays owed after a cancelled checkout; a share can simply be paid again
        conn.execute(sa.update(db.payment).where(db.payment.c.id == p)
                     .values(status="due" if row["kind"] == "correction" else "cancelled"))
        record.append(conn, row["family_id"], "payment.cancelled", {"payment_id": p}, actor(s), now=now())
    return RedirectResponse(f"/f/{row['family_id']}/expenses/{row['expense_id']}", status_code=303)
