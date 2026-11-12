"""The ledger feed behind Money & Time: one family's money and its clocks, as rows for AG Studio and Bryntum.

Built on the server from what this parent may already see. Every query is scoped to the session's family.
Never included: private answers, unapproved drafts, the agreement's full text, consent notes, PayPal emails.
Amounts come from stored decisions (the engine) and PayPal read-backs; nothing here decides anything.
"""
from __future__ import annotations

import json
from datetime import date

import sqlalchemy as sa

from between import db, engine as E, ruleset as RS
from between.reconcile import counts_as_paid
from between.web.present import category_name
from between.web.routes_expenses import _history
from between.web.routes_family import labels
from between.web.summary import family_summary


def _usd(minor: int | None) -> float | None:
    return None if minor is None else minor / 100


def _rules_by_hash(conn, fid: str, cache: dict, rs_hash: str) -> tuple[str | None, dict]:
    if rs_hash not in cache:
        row = conn.execute(sa.select(db.ruleset.c.id, db.ruleset.c.json).where(
            db.ruleset.c.family_id == fid, db.ruleset.c.hash == rs_hash)).first() if rs_hash else None
        cache[rs_hash] = (row.id, {r["id"]: r for r in json.loads(row.json)["rules"]}) if row else (None, {})
    return cache[rs_hash]


def _clause(r: dict) -> str:
    return f"§{r['source']['section']} p.{r['source']['page']}"


def _settled(p: dict | None) -> str:
    if p is None:
        return "none"
    if counts_as_paid(p):
        return "verified"
    return "outside" if p["status"] == "outside" else "pending"


def family_feed(conn, s, today: date) -> dict:
    fid = s.family_id
    names = labels(conn, fid)
    decisions = {r.expense_id: (json.loads(r.json), r.ruleset_hash) for r in conn.execute(
        sa.select(db.decision.c.expense_id, db.decision.c.json, db.decision.c.ruleset_hash)
        .join(db.expense, db.expense.c.id == db.decision.c.expense_id).where(db.expense.c.family_id == fid))}
    pays = [dict(p) for p in conn.execute(
        sa.select(db.payment).join(db.expense, db.expense.c.id == db.payment.c.expense_id)
        .where(db.expense.c.family_id == fid, db.payment.c.status.not_in(("failed", "declined", "cancelled")))).mappings()]
    share = {p["expense_id"]: p for p in pays if p["kind"] == "share"}

    expenses, obligations, clauses, rule_cache = [], [], [], {}
    for e in sorted(family_summary(conn, s)["expenses"], key=lambda e: (e["incurred_on"], e["id"])):
        eid = e["id"]
        expenses.append({"id": eid, "date": e["incurred_on"], "requestedOn": e["requested_on"], "category": e["category"],
                         "categoryName": category_name(e["category"]), "paidBy": e["paid_by"],
                         "paidByName": names.get(e["paid_by"], e["paid_by"]), "amount": _usd(e["amount_minor"]),
                         "amountMinor": e["amount_minor"], "status": e["status"], "label": e["label"],
                         "href": f"/f/{fid}/expenses/{eid}"})
        d, rs_hash = decisions.get(eid, ({}, ""))
        rsid, rules = _rules_by_hash(conn, fid, rule_cache, rs_hash)
        cited = [rules[c["rule"]] for c in d.get("cite", []) if "rule" in c and c["rule"] in rules]
        for r in cited:
            clauses.append({"expenseId": eid, "section": r["source"]["section"], "page": r["source"]["page"],
                            "quote": r["source"]["quote"], "href": f"/f/{fid}/source?rs={rsid}&r={r['id']}#clause"})
        if d.get("status") == "payable" and d.get("due_on"):
            settled = _settled(share.get(eid))
            state = settled if settled in ("verified", "outside") else ("overdue" if d["due_on"] < today.isoformat() else "open")
            deadline = next((r for r in cited if r["kind"] == "payment_deadline_days"), None)
            obligations.append({"id": f"w{eid}", "kind": "pay-window", "expenseId": eid, "start": e["requested_on"],
                                "end": d["due_on"], "owedBy": d["owed_by"], "owedTo": d["owed_to"],
                                "amount": _usd(d["amount_minor"]), "amountMinor": d["amount_minor"], "state": state,
                                "category": e["category"], "clause": _clause(deadline) if deadline else None})

    for c in conn.execute(sa.select(db.consent).where(db.consent.c.family_id == fid)).mappings():
        on = c["given_on"] or today.isoformat()
        obligations.append({"id": f"c{c['id']}", "kind": "consent", "expenseId": c["used_by_expense_id"], "start": on,
                            "end": on, "owedBy": None, "owedTo": None, "amount": _usd(c["max_minor"]),
                            "amountMinor": c["max_minor"], "state": "agreed" if c["given_by"] else "asked",
                            "category": c["category"], "clause": None})

    payments = [{"id": p["id"], "expenseId": p["expense_id"], "kind": p["kind"], "payer": p["payer_role"],
                 "payee": p["payee_role"], "amount": _usd(p["amount_minor"]), "paypalStatus": p["paypal_status"],
                 "verification": p["verification"],
                 "verifiedAt": p["last_verified_at"].isoformat() if p["last_verified_at"] else None,
                 "gross": _usd(p["gross_minor"]), "fee": _usd(p["fee_minor"]), "net": _usd(p["net_minor"]),
                 "settled": _settled(p)} for p in pays]

    caps = []
    rs, approvals = RS.current(conn, fid)
    if rs and E.is_approved(rs, approvals):
        history = _history(conn, fid, "")
        for r in rs["rules"]:
            if r["kind"] != "annual_cap":
                continue
            cap = r["params"]["per_parent_minor"]
            for party in ("A", "B"):
                used = E.annual_cap_used(history, r["category"], today.year, party)
                caps.append({"category": r["category"], "categoryName": category_name(r["category"]), "party": party,
                             "partyName": names.get(party, party), "cap": _usd(cap), "used": _usd(used),
                             "left": _usd(max(0, cap - used)), "clause": _clause(r)})

    return {"asOf": today.isoformat(), "names": names, "expenses": expenses, "obligations": obligations,
            "payments": payments, "clauses": clauses, "caps": caps}
