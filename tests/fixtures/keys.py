"""Hand-written answer keys for the three synthetic agreements: what a careful human would extract.
Used to score the model and as the approved rule sets in the engine tests."""

def R(id, kind, cat, params, quote, page, section):
    return {"id": id, "kind": kind, "category": cat, "params": params,
            "source": {"quote": quote, "page": page, "section": section}}


def A(cat, affects, quote, page, section, question):
    return {"category": cat, "affects": affects, "question": question,
            "source": {"quote": quote, "page": page, "section": section}}


PLAN1 = {
    "doc": "plan1_rivera_okafor.txt",
    "parties": {"A": "Mother", "B": "Father"},
    "rules": [
        R("p1-med", "split", "medical", {"shares": {"A": 40, "B": 60}},
          "shall be paid 60% by the Father and 40% by the Mother", 2, "6.1"),
        R("p1-ext", "split", "extracurricular", {"shares": {"A": 50, "B": 50}},
          "The parents shall share the cost of extracurricular activities equally, 50% each.", 2, "6.2"),
        R("p1-ext-consent", "consent_required", "extracurricular", {"over_minor": 20000},
          "Neither parent shall enrol the Child in an activity costing more than $200 without the prior written consent of the other parent.", 2, "6.2"),
        R("p1-ext-cap", "annual_cap", "extracurricular", {"per_parent_minor": 150000},
          "Neither parent shall be required to contribute more than $1,500 per calendar year toward extracurricular activities.", 2, "6.3"),
        R("p1-edu", "split", "education", {"shares": {"A": 50, "B": 50}},
          "Tutoring, school trips and school fees shall be shared equally, 50% each.", 2, "6.4"),
        R("p1-receipt", "receipt_required", "*", {}, "with a copy of the receipt", 3, "7.1"),
        R("p1-req", "request_deadline_days", "*", {"days": 30},
          "within 30 days of paying the expense", 3, "7.1"),
        R("p1-pay", "payment_deadline_days", "*", {"days": 14},
          "The other parent shall pay their share within 14 days of receiving a complete request.", 3, "7.2"),
        R("p1-clothing", "not_shared", "clothing", {}, "Clothing, gifts and everyday food are not shared expenses", 3, "7.3"),
        R("p1-gifts", "not_shared", "gifts", {}, "Clothing, gifts and everyday food are not shared expenses", 3, "7.3"),
        R("p1-food", "not_shared", "food", {}, "Clothing, gifts and everyday food are not shared expenses", 3, "7.3"),
    ],
    "ambiguities": [],
}

PLAN2 = {
    "doc": "plan2_crossborder.txt",
    "parties": {"A": "Parent One", "B": "Parent Two"},
    "rules": [
        R("p2-med", "split", "medical", {"shares": {"A": 65, "B": 35}},
          "currently 65% Parent One and 35% Parent Two", 2, "4(a)"),
        R("p2-med-consent", "consent_required", "medical", {"over_minor": 50000},
          "Any non-emergency health expense over $500 requires the written agreement of both parents before it is incurred.", 2, "4(b)"),
        R("p2-med-emerg", "emergency_exception", "medical", {"notify_hours": 48},
          "In an emergency, the treating parent may proceed without agreement and must notify the other parent within 48 hours.", 2, "4(c)"),
        R("p2-travel-parent", "not_shared", "travel_parent", {},
          "Each parent bears their own travel costs for handovers.", 3, "6(a)"),
        R("p2-travel-child", "split", "travel_child", {"shares": {"A": 50, "B": 50}},
          "The Child's return flights for the summer visit shall be split equally between the parents.", 3, "6(b)"),
        R("p2-receipt", "receipt_required", "*", {}, "with proof of payment", 3, "7(a)"),
        R("p2-pay", "payment_deadline_days", "*", {"days": 21},
          "A parent who receives a claim shall pay within 21 days.", 3, "7(b)"),
    ],
    "ambiguities": [
        A("extracurricular", "split", "Reasonable costs of activities shall be shared equally.", 2, "5(a)",
          "'Reasonable' isn't defined. Which activity costs count?"),
        A("*", "request_deadline_days", "Claims for a share of any expense shall be made promptly", 3, "7(a)",
          "'Promptly' has no number of days."),
    ],
}

PLAN3 = {
    "doc": "plan3_mediated_memo.txt",
    "parties": {"A": "Mom", "B": "Dad"},
    "rules": [
        R("p3-care", "split", "childcare", {"shares": {"A": 50, "B": 50}}, "Daycare is split 50/50.", 1, "Item 2"),
        R("p3-care-pay", "payment_deadline_days", "childcare", {"days": 10},
          "Mom reimburses him half within 10 days of his request", 1, "Item 2"),
        R("p3-consent", "consent_required", "*", {"over_minor": 30000},
          "Anything over 300 dollars has to be discussed and agreed in writing before it is paid, whatever it is for.", 2, "Item 4"),
        R("p3-camp-first", "covers_first", "camp", {"party": "B", "up_to_minor": 80000},
          "Dad covers summer camp up to $800 in total each summer.", 2, "Item 5"),
        R("p3-camp", "split", "camp", {"shares": {"A": 50, "B": 50}},
          "Any amount above $800 is split 50/50.", 2, "Item 5"),
        R("p3-supplies", "not_shared", "school_supplies", {},
          "Whoever buys school supplies pays for them. They are not shared.", 2, "Item 6"),
        R("p3-receipt", "receipt_required", "*", {}, "Reimbursement requests should include a receipt.", 3, "A.2"),
    ],
    "ambiguities": [
        A("medical", "split", "All medical costs will be split equally between Mom and Dad.", 3, "A.1",
          "Item 3 says Dad 70% / Mom 30%, but Appendix A.1 says medical is split equally. Which applies?"),
    ],
}

KEYS = [PLAN1, PLAN2, PLAN3]
