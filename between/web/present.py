"""Plain-English wording for rules, decisions and money. Templates use these; nothing here decides."""
from __future__ import annotations

from between.money import fmt_usd

CATEGORY_NAMES = {"*": "Every expense", "medical": "Medical and dental", "extracurricular": "Activities",
                  "education": "Education", "childcare": "Childcare", "camp": "Camp", "travel_child": "The child's travel",
                  "travel_parent": "Parents' own travel", "clothing": "Clothing", "gifts": "Gifts", "food": "Everyday food",
                  "school_supplies": "School supplies"}
EXPENSE_CATEGORIES = [c for c in CATEGORY_NAMES if c != "*"]


def category_name(cat: str) -> str:
    return CATEGORY_NAMES.get(cat, cat)


def describe_rule(rule: dict, labels: dict[str, str]) -> str:
    k, p, cat = rule["kind"], rule.get("params", {}), category_name(rule["category"])
    if k == "split":
        s = p["shares"]
        return f"{cat}: {labels['A']} {s['A']}%, {labels['B']} {s['B']}%"
    if k == "consent_required":
        return f"{cat}: agree in writing before spending more than {fmt_usd(p['over_minor'])}"
    if k == "emergency_exception":
        return f"{cat}: in an emergency, go ahead and tell the other parent within {p['notify_hours']} hours"
    if k == "annual_cap":
        return f"{cat}: neither parent pays more than {fmt_usd(p['per_parent_minor'])} a year"
    if k == "covers_first":
        return f"{cat}: {labels[p['party']]} pays the first {fmt_usd(p['up_to_minor'])}; the rest is split"
    if k == "request_deadline_days":
        return f"{cat}: ask for reimbursement within {p['days']} days"
    if k == "payment_deadline_days":
        return f"{cat}: pay your share within {p['days']} days of a complete request"
    if k == "not_shared":
        return f"{cat}: not shared; each parent pays their own"
    if k == "fee_policy":
        return ("Payments: the paying parent adds PayPal's estimated fee" if p.get("payer_adds")
                else "Payments: the receiving parent bears PayPal's fee")
    if k == "receipt_required":
        return f"{cat}: include a receipt"
    return f"{cat}: {k}"


STATUS_WORDS = {"payable": "Payable", "needs_consent": "Needs agreement first", "needs_parents": "Needs both of you",
                "rejected": "Not shared under your rules", "refused": "Can't be decided yet"}
REASON_WORDS = {"not_shared": "Your agreement says each parent pays their own for this.",
                "receipt_missing": "Your agreement asks for a receipt.",
                "requested_too_late": "This was requested after the deadline in your agreement.",
                "prior_consent_missing": "Your agreement needs the other parent's written agreement before spending this much.",
                "open_question": "Your agreement is unclear here, and you haven't settled it in Between yet.",
                "no_rule_for_category": "Your approved rules don't cover this kind of expense.",
                "ruleset_not_approved_by_both": "Both of you need to approve the current rules first.",
                "bad_expense": "Something about this expense doesn't add up."}
