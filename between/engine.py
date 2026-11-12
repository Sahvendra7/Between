"""The deterministic decision. Pure: no I/O, no model. Fails closed.

Agreement rules come from the text; operational resolutions only fill an open question and
never change the legal agreement. Nothing runs unless both parents approved this exact version.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import date

from between.money import fee_estimate, split_amount

PARTIES = ("A", "B")
BLOCKING = {"split", "not_shared", "covers_first", "annual_cap", "consent_required"}


def ruleset_hash(ruleset: dict) -> str:
    core = {"parties": ruleset["parties"], "rules": sorted(ruleset["rules"], key=lambda r: r["id"]),
            "questions": ruleset.get("questions", [])}
    return hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def is_approved(ruleset: dict, approvals: dict[str, str]) -> bool:
    h = ruleset_hash(ruleset)
    return all(approvals.get(p) == h for p in PARTIES)


def _find(rules, kind, cat):
    specific = [r for r in rules if r["kind"] == kind and r["category"] == cat]
    return specific[0] if specific else next((r for r in rules if r["kind"] == kind and r["category"] == "*"), None)


def _cite(r: dict) -> dict:
    if r.get("origin") == "resolution":
        return {"resolution": r["id"]}
    return {"rule": r["id"], "section": r["source"]["section"], "page": r["source"]["page"]}


def _q_cite(q: dict) -> dict:
    return {"question": q.get("id"), "section": q["source"].get("section"), "page": q["source"].get("page")}


def _valid_consent(consents, expense, other, cat, amount, incurred):
    for c in consents:
        try:
            given_on = date.fromisoformat(c["given_on"]) if c.get("given_on") else None
        except ValueError:
            continue
        if (c.get("category") == cat and isinstance(c.get("max_minor"), int) and amount <= c["max_minor"]
                and c.get("given_by") == other and given_on is not None and given_on <= incurred
                and c.get("used_by_expense_id") in (None, expense.get("id"))):
            return c
    return None


def annual_cap_used(history: Sequence[dict], category: str, year: int, party: str) -> int:
    """What `party` has already carried in `category` this `year`, as an annual cap counts it."""
    return sum(h["owed_minor"] if h["owed_by"] == party else h["amount_minor"] - h["owed_minor"]
               for h in history if h["category"] == category and h["year"] == year
               and party in (h["owed_by"], h["paid_by"]))


def evaluate(ruleset: dict, approvals: dict[str, str], expense: dict,
             consents: Sequence[dict] = (), history: Sequence[dict] = ()) -> dict:
    if not is_approved(ruleset, approvals):
        return {"status": "refused", "reason": "ruleset_not_approved_by_both"}
    try:
        amount, payer, cat = expense["amount_minor"], expense["paid_by"], expense["category"]
        incurred, requested = date.fromisoformat(expense["incurred_on"]), date.fromisoformat(expense["requested_on"])
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0 or payer not in PARTIES or requested < incurred:
            raise ValueError
    except (KeyError, ValueError, TypeError):
        return {"status": "refused", "reason": "bad_expense"}
    other = "B" if payer == "A" else "A"
    rules, cites, notes = ruleset["rules"], [], []
    resolved = {r["source"].get("question_id") for r in rules if r.get("origin") == "resolution"}

    if (r := _find(rules, "not_shared", cat)) and r["category"] == cat:
        return {"status": "rejected", "reason": "not_shared", "cite": [_cite(r)]}
    for q in ruleset.get("questions", []):
        if q.get("type") == "fee_policy":  # a Between setting, not an unclear clause
            continue
        if q.get("category") in (cat, "*") and q.get("id") not in resolved:
            if q.get("affects") in BLOCKING:
                return {"status": "needs_parents", "reason": "open_question", "question": q.get("question"),
                        "question_id": q.get("id"), "cite": [_q_cite(q)]}
            notes.append({"unchecked": q.get("affects"), "section": q["source"].get("section")})
    split = _find(rules, "split", cat)
    if not split:
        return {"status": "needs_parents", "reason": "no_rule_for_category"}
    cites.append(_cite(split))
    if (r := _find(rules, "receipt_required", cat)) and not expense.get("receipt"):
        return {"status": "rejected", "reason": "receipt_missing", "cite": [_cite(r)]}
    if (r := _find(rules, "request_deadline_days", cat)) and (requested - incurred).days > r["params"]["days"]:
        return {"status": "rejected", "reason": "requested_too_late", "cite": [_cite(r)]}
    consent_used = None
    if (r := _find(rules, "consent_required", cat)) and amount > r["params"]["over_minor"]:
        emergency = _find(rules, "emergency_exception", cat)
        if expense.get("emergency") and emergency:
            notes.append({"emergency": True, "notify_within_hours": emergency["params"]["notify_hours"]})
            cites.append(_cite(emergency))
        elif c := _valid_consent(consents, expense, other, cat, amount, incurred):
            consent_used = c["id"]
            cites.append(_cite(r))
        else:
            return {"status": "needs_consent", "reason": "prior_consent_missing", "cite": [_cite(r)]}

    year, owed, base = incurred.year, 0, amount
    if r := _find(rules, "covers_first", cat):
        before = sum(h["amount_minor"] for h in history if h["category"] == cat and h["year"] == year)
        cover_now = min(amount, max(0, r["params"]["up_to_minor"] - before))
        base = amount - cover_now
        if r["params"]["party"] == other:
            owed += cover_now
        cites.append(_cite(r))
    owed += split_amount(base, split["params"]["shares"])[other]
    if r := _find(rules, "annual_cap", cat):
        room = max(0, r["params"]["per_parent_minor"] - annual_cap_used(history, cat, year, other))
        if owed > room:
            notes.append({"capped_from": owed})
            owed = room
        cites.append(_cite(r))
    due = None
    if r := _find(rules, "payment_deadline_days", cat):
        due = date.fromordinal(requested.toordinal() + r["params"]["days"]).isoformat()
        cites.append(_cite(r))
    if (r := _find(rules, "fee_policy", "*")) and r["params"].get("payer_adds") and owed > 0:
        notes.append({"fee_added_estimate": fee_estimate(owed)})
        owed += notes[-1]["fee_added_estimate"]
        cites.append(_cite(r))
    out = {"status": "payable", "owed_by": other, "owed_to": payer, "amount_minor": owed,
           "due_on": due, "cite": cites, "notes": notes}
    if consent_used:
        out["consent_id"] = consent_used
    return out
