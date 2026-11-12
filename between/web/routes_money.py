"""Money & Time: the family's year on one screen (AG Studio report + Bryntum calendar), from one authorised feed."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

import json
import logging

import sqlalchemy as sa

from fastapi.responses import JSONResponse

from between import access, db, demo, engine as E, money_ai as M, ruleset as RS
from between.money import fmt_usd
from between.web.deps import checked_form, get_conn, now, render, require_family
from between.web.ledger import family_feed
from between.web.present import EXPENSE_CATEGORIES
from between.web.routes_calendar import calendar_data
from between.web.ledger import _settled
from between.web.routes_expenses import _consents, _expense, _history, citations, live_payment
from between.web.routes_family import labels

router = APIRouter()

# AG Studio (commercial, loaded from jsDelivr, pinned with SRI, never vendored) injects <style> tags, so this page
# alone allows inline styles. Scripts stay limited to this origin and the one pinned CDN file.
MONEY_CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
             "script-src 'self' https://cdn.jsdelivr.net; connect-src 'self'; form-action 'self'; "
             "frame-ancestors 'none'; base-uri 'none'")
AG_STUDIO_SRC = "https://cdn.jsdelivr.net/npm/ag-studio@3.1.0/dist/umd/ag-studio.min.js"
AG_STUDIO_SRI = "sha384-AQulWK/PF30iLAso56dIH/1+Iv852aUbFC98K7N1ZpLYVvmamIEAU36dEbUaPym1"


@router.get("/f/{fid}/money")
def money_page(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    settings = request.app.state.settings
    rs, approvals = RS.current(conn, fid)
    resp = render(request, "money.html", s=s, fid=fid, feed=family_feed(conn, s, now().date()),
                  approved=bool(rs and E.is_approved(rs, approvals)),
                  demo_family=settings.demo_mode and demo.is_visitor_family(conn, fid),
                  studio_src=AG_STUDIO_SRC, studio_sri=AG_STUDIO_SRI, license=settings.ag_studio_license,
                  ai_enabled=bool(settings.money_ai and settings.demo_mode and settings.gemini_api_key))
    resp.headers["Content-Security-Policy"] = MONEY_CSP
    return resp


@router.get("/f/{fid}/money.json")
def money_json(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    feed = family_feed(conn, s, now().date())
    cal, names = calendar_data(conn, s), feed["names"]
    for o in feed["obligations"]:
        if o["kind"] == "pay-window":  # endDate is exclusive in Bryntum: the due day stays inside the bar
            end = (date.fromisoformat(o["end"]) + timedelta(days=1)).isoformat()
            cal["events"].append({
                "id": o["id"], "kind": "pay-window", "state": o["state"], "expenseId": o["expenseId"], "allDay": True,
                "startDate": o["start"], "endDate": end, "resourceId": o["owedBy"],
                "name": f"{names[o['owedBy']]} → {names[o['owedTo']]} {fmt_usd(o['amountMinor'])} · due {o['end']}"
                        f"{' · ' + o['clause'] if o['clause'] else ''} · {PAY_STATE[o['state']]}"})
    return {**feed, "calendar": cal}


PAY_STATE = {"open": "open", "overdue": "overdue", "verified": "verified with PayPal",
             "outside": "settled outside Between"}


@router.post("/f/{fid}/money/preview")
async def preview_expense(request: Request, fid: str, conn=Depends(get_conn)):
    """What the rules engine would decide for a hypothetical expense. Read-only: nothing is stored."""
    s = require_family(request, conn, fid)
    if not access.check_csrf(s, request.headers.get("x-csrf-token")):
        raise HTTPException(status_code=403, detail="Reload the page and try again.")
    try:
        body = await request.json()
        cat, amount, paid_by = body["category"], body["amountMinor"], body["paidBy"]
        incurred = date.fromisoformat(body["incurredOn"]).isoformat()
        if cat not in EXPENSE_CATEGORIES or type(amount) is not int or amount <= 0 or paid_by not in ("A", "B"):
            raise ValueError
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Give a category, a whole number of cents, a date and who pays.") from None
    rs, approvals = RS.current(conn, fid)
    if not rs:
        return {"status": "refused", "reason": "no_rules", "cite": []}
    exp = {"id": "preview", "category": cat, "amount_minor": amount, "paid_by": paid_by, "incurred_on": incurred,
           "requested_on": incurred, "receipt": True, "emergency": False}
    d = E.evaluate(rs, approvals, exp, _consents(conn, fid), _history(conn, fid, ""))
    rules = {r["id"]: r for r in rs["rules"]}
    cite = [{"section": rules[c["rule"]]["source"]["section"], "page": rules[c["rule"]]["source"]["page"],
             "quote": rules[c["rule"]]["source"]["quote"]} for c in d.get("cite", []) if c.get("rule") in rules]
    return {"status": d["status"], "reason": d.get("reason"), "owedBy": d.get("owed_by"), "owedTo": d.get("owed_to"),
            "amountMinor": d.get("amount_minor"), "dueOn": d.get("due_on"), "notes": d.get("notes", []), "cite": cite}


@router.post("/f/{fid}/money/sample-year")
async def sample_year(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    await checked_form(request, s)
    try:
        demo.add_sample_year(conn, fid, s, now().date())
    except ValueError as e:
        code = str(e)
        detail = {"not_demo": "Sample years are only for demo families.",
                  "not_approved": "Approve your rules (both of you) first, so Between can decide each expense.",
                  "already_added": "This family already has its sample year."}[code]
        raise HTTPException(status_code=403 if code == "not_demo" else 409, detail=detail) from None
    return RedirectResponse(f"/f/{fid}/money", status_code=303)


log = logging.getLogger("between.ai")


@router.post("/f/{fid}/money/ai")
async def ledger_guide_turn(request: Request, fid: str, conn=Depends(get_conn)):
    """One AG Studio agent turn, forwarded to Gemini. The agent's tools are read-only; this route only relays."""
    s = require_family(request, conn, fid)
    settings = request.app.state.settings
    if not (settings.money_ai and settings.demo_mode and settings.gemini_api_key):
        raise HTTPException(status_code=404)
    if not access.check_csrf(s, request.headers.get("x-csrf-token")):
        raise HTTPException(status_code=403, detail="Reload the page and try again.")
    raw = await request.body()
    if len(raw) > M.MAX_BODY:
        return JSONResponse(M.failed("That conversation is too long. Start a new one."), status_code=413)
    try:
        req = json.loads(raw)
        body = M.to_chat(req, M.SIGS)
    except (ValueError, KeyError, TypeError, AttributeError):
        return JSONResponse(M.failed("The guide couldn't read that request."), status_code=400)
    with request.app.state.engine.begin() as budget:  # committed now, not after the slow model call
        within = M.charge(budget, fid, now())
    if not within:
        return JSONResponse(M.failed("The guide is resting this hour. The calendar and report still work."), status_code=429)
    status, resp = M.call_gemini(body, settings.gemini_api_key)
    log.info("ledger guide turn: family=%s status=%s", fid, status)
    if status != 200 or not resp:
        return M.failed("The guide couldn't answer right now. The calendar and report still work.")
    return M.from_chat(resp, M.SIGS)


@router.get("/f/{fid}/money/expense/{eid}.json")
def expense_json(request: Request, fid: str, eid: str, conn=Depends(get_conn)):
    """The stored decision for one expense, with the clauses it cites, for the Ledger guide. Read-only."""
    s = require_family(request, conn, fid)
    e = _expense(conn, fid, eid)  # 404 unless it's this family's
    drow = conn.execute(sa.select(db.decision).where(db.decision.c.expense_id == eid)).mappings().first()
    d = json.loads(drow["json"]) if drow else {"status": "undecided"}
    names = labels(conn, fid)
    cites = citations(conn, drow["ruleset_hash"], d, names, fid) if drow else []
    pay = live_payment(conn, eid, "share")
    return {"expenseId": eid, "category": e["category"], "expenseAmountMinor": e["amount_minor"], "paidBy": e["paid_by"],
            "incurredOn": e["incurred_on"], "requestedOn": e["requested_on"], "status": d.get("status"),
            "reason": d.get("reason"), "owedBy": d.get("owed_by"), "owedTo": d.get("owed_to"),
            "amountMinor": d.get("amount_minor"), "dueOn": d.get("due_on"), "names": names,
            "payment": {"settled": _settled(pay), "verifiedAt": pay["last_verified_at"].isoformat()
                        if pay and pay["last_verified_at"] else None},
            "cite": [{"section": c.get("section"), "page": c.get("page"), "quote": x["quote"], "rule": x["what"], "href": x.get("href")}
                     for c, x in zip(d.get("cite", []), cites) if x["quote"]]}
