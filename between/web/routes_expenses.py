"""Expenses: the receipt is read in memory, the payer confirms the amount, the engine decides."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, timedelta

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError

from between import db, demo, engine as E, record, ruleset as RS
from between.extraction import AIUnavailable, read_receipt
from between.money import MoneyError, fmt_usd, parse_usd
from between.web.deps import actor, checked_form, get_conn, now, render, require_family
from between.web.present import EXPENSE_CATEGORIES
from between.web.routes_family import labels

router = APIRouter()
MONEY_ERRORS = {"empty": "Enter the amount you paid.", "format": "Enter an amount like 420.00.",
                "too_many_decimals": "Use at most two decimal places.", "not_positive": "The amount must be more than zero.",
                "too_large": "That's more than this demo handles."}
REDECIDABLE = {"needs_consent", "needs_parents", "refused"}


def _today() -> date:
    return now().date()


def _expense(conn, fid, eid) -> dict:
    row = conn.execute(sa.select(db.expense).where(db.expense.c.id == eid, db.expense.c.family_id == fid)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404)
    return dict(row)


def _history(conn, fid, exclude_id) -> list[dict]:
    q = (sa.select(db.expense, db.decision.c.json).join(db.decision, db.decision.c.expense_id == db.expense.c.id)
         .where(db.expense.c.family_id == fid, db.expense.c.id != exclude_id))
    out = []
    for r in conn.execute(q).mappings():
        d = json.loads(r["json"])
        if d.get("status") == "payable":
            out.append({"category": r["category"], "year": int(r["incurred_on"][:4]), "amount_minor": r["amount_minor"],
                        "paid_by": r["paid_by"], "owed_by": d["owed_by"], "owed_minor": d["amount_minor"]})
    return out


def _consents(conn, fid) -> list[dict]:
    return [dict(r) for r in conn.execute(sa.select(db.consent).where(db.consent.c.family_id == fid)).mappings()]


def decide(conn, fid, expense: dict, s) -> dict:
    rs, approvals = RS.current(conn, fid)
    exp = {"id": expense["id"], "category": expense["category"], "amount_minor": expense["amount_minor"],
           "paid_by": expense["paid_by"], "incurred_on": expense["incurred_on"], "requested_on": expense["requested_on"],
           "receipt": bool(expense["receipt_sha256"]), "emergency": bool(expense["emergency"])}
    d = E.evaluate(rs, approvals, exp, _consents(conn, fid), _history(conn, fid, expense["id"])) if rs else \
        {"status": "refused", "reason": "ruleset_not_approved_by_both"}
    rs_hash = rs["hash"] if rs else ""
    d_json = json.dumps(d, sort_keys=True)
    d_hash = hashlib.sha256(f"{expense['id']}|{rs_hash}|{d_json}".encode()).hexdigest()
    t = now()
    conn.execute(sa.delete(db.decision).where(db.decision.c.expense_id == expense["id"]))
    conn.execute(sa.insert(db.decision).values(expense_id=expense["id"], ruleset_hash=rs_hash, json=d_json, hash=d_hash, at=t))
    conn.execute(sa.update(db.expense).where(db.expense.c.id == expense["id"]).values(status=d["status"]))
    if cid := d.get("consent_id"):
        conn.execute(sa.update(db.consent).where(db.consent.c.id == cid).values(used_by_expense_id=expense["id"]))
    record.append(conn, fid, "expense.decided", {
        "expense_id": expense["id"], "status": d["status"], "reason": d.get("reason"), "owed_by": d.get("owed_by"),
        "amount_minor": d.get("amount_minor"), "due_on": d.get("due_on"), "decision_hash": d_hash, "ruleset_hash": rs_hash,
        "cite": [c.get("section") or c.get("resolution") for c in d.get("cite", [])]}, actor(s), now=t)
    return d


@router.get("/f/{fid}/expenses/new")
def new_expense(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    rs, _ = RS.current(conn, fid)
    emergency = bool(rs and any(r["kind"] == "emergency_exception" for r in rs["rules"]))
    return render(request, "expense_new.html", s=s, fid=fid, categories=EXPENSE_CATEGORIES, today=_today().isoformat(),
                  emergency_allowed=emergency)


@router.post("/f/{fid}/expenses/new")
async def read_expense(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    form = await checked_form(request, s)
    settings = request.app.state.settings
    category, incurred = form.get("category", ""), form.get("incurred_on") or _today().isoformat()
    ctx = dict(s=s, fid=fid, categories=EXPENSE_CATEGORIES, today=_today().isoformat(), emergency_allowed=True)
    if category not in EXPENSE_CATEGORIES:
        return render(request, "expense_new.html", 400, error="Choose what kind of expense this is.", **ctx)
    try:
        when = date.fromisoformat(incurred)
    except ValueError:
        return render(request, "expense_new.html", 400, error="Enter the date you paid.", **ctx)
    if when > _today() or when < _today() - timedelta(days=366):
        return render(request, "expense_new.html", 400, error="The date must be within the last year and not in the future.", **ctx)
    upload = form.get("receipt")
    sha, guess = None, None
    if upload is not None and getattr(upload, "filename", ""):
        data = await upload.read()
        try:
            demo.check_upload(upload.content_type, len(data), settings)
        except demo.DemoGuard as g:
            return render(request, "expense_new.html", 400, error=g.message, **ctx)
        sha = hashlib.sha256(data).hexdigest()
        if conn.execute(sa.select(db.expense.c.id).where(db.expense.c.family_id == fid, db.expense.c.receipt_sha256 == sha)).first():
            return render(request, "expense_new.html", 409, error="This receipt was already submitted.", **ctx)
        try:
            guess = read_receipt(data, upload.content_type, client=request.app.state.ai)
        except AIUnavailable:
            guess = None
        del data  # the receipt is never stored: only its hash and the confirmed amount
    amount = f"{guess.total_minor / 100:.2f}" if guess and guess.total_minor else ""
    return render(request, "expense_confirm.html", s=s, fid=fid, category=category, incurred_on=when.isoformat(),
                  receipt_sha256=sha or "", emergency="on" if form.get("emergency") else "", amount=amount,
                  merchant=guess.merchant if guess else None)


@router.post("/f/{fid}/expenses/confirm")
async def confirm_expense(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    form = await checked_form(request, s)
    category, incurred, sha = form.get("category", ""), form.get("incurred_on", ""), form.get("receipt_sha256") or None
    ctx = dict(s=s, fid=fid, category=category, incurred_on=incurred, receipt_sha256=sha or "",
               emergency=form.get("emergency", ""), amount=form.get("amount", ""), merchant=None)
    try:
        cents = parse_usd(form.get("amount", ""))
    except MoneyError as e:
        return render(request, "expense_confirm.html", 400, error=MONEY_ERRORS[e.code], **ctx)
    if category not in EXPENSE_CATEGORIES:
        raise HTTPException(status_code=400)
    try:
        date.fromisoformat(incurred)
    except ValueError:
        raise HTTPException(status_code=400) from None
    eid, t = uuid.uuid4().hex[:12], now()
    row = {"id": eid, "family_id": fid, "paid_by": s.role, "category": category, "amount_minor": cents, "incurred_on": incurred,
           "requested_on": t.date().isoformat(), "receipt_sha256": sha, "emergency": bool(form.get("emergency")), "status": "submitted"}
    try:
        with conn.begin_nested():
            conn.execute(sa.insert(db.expense).values(**row))
    except IntegrityError:
        return render(request, "expense_confirm.html", 409, error="This receipt was already submitted.", **ctx)
    record.append(conn, fid, "expense.submitted", {"expense_id": eid, "category": category, "amount_minor": cents,
                                                   "paid_by": s.role, "incurred_on": incurred, "receipt_sha256": sha}, actor(s), now=t)
    decide(conn, fid, row, s)
    return RedirectResponse(f"/f/{fid}/expenses/{eid}", status_code=303)


def citations(conn, rs_hash: str, decision: dict, names: dict) -> list[dict]:
    from between.web.present import describe_rule
    row = conn.execute(sa.select(db.ruleset.c.json).where(db.ruleset.c.hash == rs_hash)).first() if rs_hash else None
    rules = {r["id"]: r for r in json.loads(row.json)["rules"]} if row else {}
    out = []
    for c in decision.get("cite", []):
        if "resolution" in c:
            r = rules.get(c["resolution"])
            out.append({"label": f"Resolution {c['resolution']}", "what": describe_rule(r, names) if r else "", "quote": None})
        elif "rule" in c:
            r = rules.get(c["rule"])
            out.append({"label": f"Page {c['page']} · {c['section']}", "what": describe_rule(r, names) if r else "",
                        "quote": r["source"]["quote"] if r else None})
        else:
            out.append({"label": f"Page {c.get('page')} · {c.get('section')}", "what": "Open question", "quote": None})
    return out


@router.get("/f/{fid}/expenses/{eid}")
def expense_page(request: Request, fid: str, eid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    e = _expense(conn, fid, eid)
    drow = conn.execute(sa.select(db.decision).where(db.decision.c.expense_id == eid)).mappings().first()
    d = json.loads(drow["json"]) if drow else {"status": "refused"}
    names = labels(conn, fid)
    pays = [dict(p) for p in conn.execute(sa.select(db.payment).where(db.payment.c.expense_id == eid)
                                          .order_by(db.payment.c.id)).mappings()]
    from between.reconcile import counts_as_paid
    live = next((p for p in pays if p["status"] not in ("failed", "declined", "cancelled")), None)
    paid = bool(live and counts_as_paid(live))
    can_pay = d.get("status") == "payable" and s.role == d.get("owed_by") and not paid and e["status"] != "reopened"
    return render(request, "decision.html", s=s, fid=fid, e=e, d=d, names=names, cites=citations(conn, drow["ruleset_hash"] if drow else "", d, names),
                  payment=live, paid=paid, can_pay=can_pay, can_redecide=d.get("status") in REDECIDABLE,
                  decision_hash=drow["hash"] if drow else "")


@router.post("/f/{fid}/expenses/{eid}/redecide")
async def redecide(request: Request, fid: str, eid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    await checked_form(request, s)
    e = _expense(conn, fid, eid)
    if e["status"] not in REDECIDABLE:
        raise HTTPException(status_code=409, detail="This expense is already decided.")
    decide(conn, fid, e, s)
    return RedirectResponse(f"/f/{fid}/expenses/{eid}", status_code=303)


@router.post("/f/{fid}/consents")
async def request_consent(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    form = await checked_form(request, s)
    category = form.get("category", "")
    try:
        cents = parse_usd(form.get("max", ""))
    except MoneyError as e:
        raise HTTPException(status_code=400, detail=MONEY_ERRORS[e.code]) from None
    if category not in EXPENSE_CATEGORIES:
        raise HTTPException(status_code=400)
    cid, t = uuid.uuid4().hex[:12], now()
    conn.execute(sa.insert(db.consent).values(id=cid, family_id=fid, requested_by=s.role, category=category, max_minor=cents,
                                              note=(form.get("note") or "")[:500]))
    record.append(conn, fid, "consent.requested", {"consent_id": cid, "category": category, "max_minor": cents}, actor(s), now=t)
    return RedirectResponse(f"/f/{fid}", status_code=303)


@router.post("/f/{fid}/consents/{cid}/agree")
async def agree_consent(request: Request, fid: str, cid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    await checked_form(request, s)
    c = conn.execute(sa.select(db.consent).where(db.consent.c.id == cid, db.consent.c.family_id == fid)).mappings().first()
    if c is None:
        raise HTTPException(status_code=404)
    if c["requested_by"] == s.role or c["given_by"]:
        raise HTTPException(status_code=403, detail="Only the other parent can agree, once.")
    t = now()
    conn.execute(sa.update(db.consent).where(db.consent.c.id == cid).values(given_by=s.role, given_on=t.date().isoformat()))
    record.append(conn, fid, "consent.given", {"consent_id": cid, "category": c["category"], "max_minor": c["max_minor"]}, actor(s), now=t)
    return RedirectResponse(f"/f/{fid}", status_code=303)


__all__ = ["router", "decide", "fmt_usd"]
