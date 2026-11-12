"""What the home page lists for a family: expenses with their state, and agreements in advance."""
from __future__ import annotations

import json

import sqlalchemy as sa

from between import db
from between.money import fmt_usd
from between.reconcile import counts_as_paid
from between.web.present import STATUS_WORDS, category_name


def _expense_state(status: str, payment: dict | None, correction: dict | None = None) -> tuple[str, str]:
    if status == "reopened":
        return "Reopened: payment refunded", "wait"
    if correction and not counts_as_paid(correction):
        return f"Amount lowered: {fmt_usd(correction['amount_minor'])} to return", "wait"
    if payment and counts_as_paid(payment):
        return "Paid · verified with PayPal", "good"
    if payment and payment["status"] in ("created", "approved", "pending"):
        return "Payment in progress", "wait"
    tone = {"payable": "wait", "rejected": "bad"}.get(status, "wait")
    return STATUS_WORDS.get(status, status), tone


def family_summary(conn, s) -> dict:
    labels = {r.role: r.label for r in conn.execute(sa.select(db.parent).where(db.parent.c.family_id == s.family_id))}
    pays, corrs = {}, {}
    for p in conn.execute(sa.select(db.payment).join(db.expense, db.expense.c.id == db.payment.c.expense_id)
                          .where(db.expense.c.family_id == s.family_id)).mappings():
        if p["status"] not in ("failed", "declined", "cancelled"):
            (pays if p["kind"] == "share" else corrs)[p["expense_id"]] = dict(p)
    expenses = []
    for e in conn.execute(sa.select(db.expense).where(db.expense.c.family_id == s.family_id)
                          .order_by(db.expense.c.requested_on.desc(), db.expense.c.id)).mappings():
        label, tone = _expense_state(e["status"], pays.get(e["id"]), corrs.get(e["id"]))
        expenses.append({**dict(e), "label": label, "tone": tone})
    consents = []
    for c in conn.execute(sa.select(db.consent).where(db.consent.c.family_id == s.family_id)).mappings():
        who = labels.get(c["requested_by"], c["requested_by"])
        if c["given_by"]:
            text = f"{category_name(c['category'])} up to {fmt_usd(c['max_minor'])}: agreed on {c['given_on']}" + \
                   (" (used)" if c["used_by_expense_id"] else "")
        else:
            text = f"{who} asks to agree in advance: {category_name(c['category'])} up to {fmt_usd(c['max_minor'])}"
        consents.append({"id": c["id"], "text": text, "can_agree": not c["given_by"] and c["requested_by"] != s.role})
    return {"expenses": expenses, "consents": consents}


__all__ = ["family_summary", "json"]
