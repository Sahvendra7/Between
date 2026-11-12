"""Engine: ported spike scenarios + resolutions + simplified single-use consent (spec r2 §6)."""
import copy
from pathlib import Path

from between import engine as E
from between import validate as V
from between.engine import ruleset_hash
from keys import PLAN1, PLAN2, PLAN3

DOCS = Path(__file__).parent.parent / "samples" / "agreements"


def approved(key, extra_rules=()):
    text = (DOCS / key["doc"]).read_text()
    v = V.validate({"rules": copy.deepcopy(key["rules"]), "ambiguities": copy.deepcopy(key["ambiguities"])},
                   text, key["parties"])
    rs = {"parties": key["parties"], "rules": v["rules"] + list(extra_rules), "questions": v["questions"]}
    h = ruleset_hash(rs)
    return rs, {"A": h, "B": h}


def exp(cat, cents, by="A", inc="2026-10-01", req="2026-10-05", receipt=True, **kw):
    return {"id": kw.pop("id", "e1"), "category": cat, "amount_minor": cents, "paid_by": by,
            "incurred_on": inc, "requested_on": req, "receipt": receipt, **kw}


def consent(cat, max_minor, by, on, used=None, cid="c1"):
    return {"id": cid, "category": cat, "max_minor": max_minor, "given_by": by, "given_on": on, "used_by_expense_id": used}


def test_one_parents_approval_is_not_enough():
    rs, ok = approved(PLAN1)
    assert E.evaluate(rs, {"A": ok["A"]}, exp("medical", 42000))["status"] == "refused"


def test_any_change_after_approval_needs_approval_again():
    rs, ok = approved(PLAN1)
    changed = copy.deepcopy(rs)
    changed["rules"][0]["params"]["shares"] = {"A": 30, "B": 70}
    assert E.evaluate(changed, ok, exp("medical", 42000))["reason"] == "ruleset_not_approved_by_both"


def test_p1_medical_share_and_due_date():
    rs, ok = approved(PLAN1)
    out = E.evaluate(rs, ok, exp("medical", 42000))
    assert (out["status"], out["owed_by"], out["amount_minor"], out["due_on"]) == ("payable", "B", 25200, "2026-10-19")
    assert {c["section"] for c in out["cite"]} == {"6.1", "7.2"}
    assert out["notes"] == [{"share_pct": 60, "share_of_minor": 42000, "share_minor": 25200}]  # the engine's own working


def test_p1_rounding_paid_by_b():
    rs, ok = approved(PLAN1)
    assert E.evaluate(rs, ok, exp("medical", 10001, by="B"))["amount_minor"] == 4000


def test_p1_activity_over_200_needs_prior_consent():
    rs, ok = approved(PLAN1)
    assert E.evaluate(rs, ok, exp("extracurricular", 25000))["status"] == "needs_consent"
    late = [consent("extracurricular", 30000, "B", "2026-10-02")]
    assert E.evaluate(rs, ok, exp("extracurricular", 25000), consents=late)["status"] == "needs_consent"
    own = [consent("extracurricular", 30000, "A", "2026-09-20")]
    assert E.evaluate(rs, ok, exp("extracurricular", 25000), consents=own)["status"] == "needs_consent"
    good = [consent("extracurricular", 30000, "B", "2026-09-20")]
    out = E.evaluate(rs, ok, exp("extracurricular", 25000), consents=good)
    assert (out["status"], out["amount_minor"], out["consent_id"]) == ("payable", 12500, "c1")


def test_consent_cap_category_and_single_use():
    rs, ok = approved(PLAN1)
    assert E.evaluate(rs, ok, exp("extracurricular", 35000), consents=[consent("extracurricular", 30000, "B", "2026-09-20")])["status"] == "needs_consent"
    assert E.evaluate(rs, ok, exp("extracurricular", 25000), consents=[consent("education", 30000, "B", "2026-09-20")])["status"] == "needs_consent"
    used = [consent("extracurricular", 30000, "B", "2026-09-20", used="e-other")]
    assert E.evaluate(rs, ok, exp("extracurricular", 25000), consents=used)["status"] == "needs_consent"
    mine = [consent("extracurricular", 30000, "B", "2026-09-20", used="e1")]
    assert E.evaluate(rs, ok, exp("extracurricular", 25000), consents=mine)["status"] == "payable"


def test_p1_annual_cap_limits_the_share():
    rs, ok = approved(PLAN1)
    hist = [{"category": "extracurricular", "year": 2026, "amount_minor": 290000, "paid_by": "A",
             "owed_by": "B", "owed_minor": 145000}]
    out = E.evaluate(rs, ok, exp("extracurricular", 15000), history=hist)
    assert out["amount_minor"] == 5000 and out["notes"] == [{"share_pct": 50, "share_of_minor": 15000, "share_minor": 7500}, {"capped_from": 7500}]


def test_p1_not_shared_late_and_missing_receipt():
    rs, ok = approved(PLAN1)
    assert E.evaluate(rs, ok, exp("clothing", 8000))["reason"] == "not_shared"
    assert E.evaluate(rs, ok, exp("medical", 8000, req="2026-11-10"))["reason"] == "requested_too_late"
    assert E.evaluate(rs, ok, exp("medical", 8000, receipt=False))["reason"] == "receipt_missing"


def test_p1_unknown_category_goes_to_the_parents():
    rs, ok = approved(PLAN1)
    assert E.evaluate(rs, ok, exp("camp", 8000))["reason"] == "no_rule_for_category"


def test_bad_input_is_refused():
    rs, ok = approved(PLAN1)
    assert E.evaluate(rs, ok, exp("medical", -5))["status"] == "refused"
    assert E.evaluate(rs, ok, exp("medical", 12.5))["status"] == "refused"
    assert E.evaluate(rs, ok, exp("medical", 500, req="2026-09-01"))["status"] == "refused"


def test_p2_non_emergency_needs_consent_emergency_does_not():
    rs, ok = approved(PLAN2)
    assert E.evaluate(rs, ok, exp("medical", 60000))["status"] == "needs_consent"
    out = E.evaluate(rs, ok, exp("medical", 60000, emergency=True))
    assert (out["status"], out["amount_minor"]) == ("payable", 21000)
    assert {"emergency": True, "notify_within_hours": 48} in out["notes"]


def test_p2_ambiguous_activities_go_to_the_parents():
    rs, ok = approved(PLAN2)
    out = E.evaluate(rs, ok, exp("extracurricular", 9000))
    assert (out["status"], out["cite"][0]["section"]) == ("needs_parents", "5(a)")


def test_p2_promptly_is_not_enforced_but_is_noted():
    rs, ok = approved(PLAN2)
    out = E.evaluate(rs, ok, exp("travel_child", 90000, by="B", req="2026-12-30"))
    assert (out["status"], out["owed_by"], out["amount_minor"], out["due_on"]) == ("payable", "A", 45000, "2027-01-20")
    assert {"unchecked": "request_deadline_days", "section": "7(a)"} in out["notes"]
    assert E.evaluate(rs, ok, exp("travel_parent", 30000))["reason"] == "not_shared"


def test_p3_contradicting_medical_clauses_go_to_the_parents():
    rs, ok = approved(PLAN3)
    assert E.evaluate(rs, ok, exp("medical", 5000))["status"] == "needs_parents"


def test_resolution_unblocks_only_its_question():
    rs, _ = approved(PLAN3)
    q = next(q for q in rs["questions"] if q["category"] == "medical")
    res = {"id": "R1", "origin": "resolution", "kind": "split", "category": "medical",
           "params": {"shares": {"A": 30, "B": 70}}, "source": {"question_id": q["id"], "answered_by": ["A", "B"]}}
    rs, ok = approved(PLAN3, extra_rules=[res])
    out = E.evaluate(rs, ok, exp("medical", 10000, by="A"))
    assert (out["status"], out["owed_by"], out["amount_minor"]) == ("payable", "B", 7000)
    assert {"resolution": "R1"} in out["cite"]
    rs2, ok2 = approved(PLAN2)
    assert E.evaluate(rs2, ok2, exp("extracurricular", 9000))["status"] == "needs_parents"


def test_p3_camp_dad_covers_first_800_then_half():
    rs, ok = approved(PLAN3)
    standing = [consent("camp", 200000, "A", "2026-05-01")]
    assert E.evaluate(rs, ok, exp("camp", 100000, by="B", inc="2026-07-01", req="2026-07-02"))["status"] == "needs_consent"
    out = E.evaluate(rs, ok, exp("camp", 100000, by="B", inc="2026-07-01", req="2026-07-02"), consents=standing)
    assert (out["owed_by"], out["amount_minor"]) == ("A", 10000)
    hist = [{"category": "camp", "year": 2026, "amount_minor": 100000, "paid_by": "B", "owed_by": "A", "owed_minor": 10000}]
    out = E.evaluate(rs, ok, exp("camp", 20000, by="A", inc="2026-08-01", req="2026-08-02"), history=hist)
    assert (out["owed_by"], out["amount_minor"]) == ("B", 10000)


def test_p3_camp_paid_by_mom_dad_owes_his_first_800():
    rs, ok = approved(PLAN3)
    out = E.evaluate(rs, ok, exp("camp", 25000, by="A", inc="2026-07-01", req="2026-07-02"))
    assert (out["owed_by"], out["amount_minor"]) == ("B", 25000)


def test_p3_daycare_over_300_literal_reading_needs_consent():
    rs, ok = approved(PLAN3)
    assert E.evaluate(rs, ok, exp("childcare", 60000, by="B"))["status"] == "needs_consent"
    out = E.evaluate(rs, ok, exp("childcare", 60000, by="B"), consents=[consent("childcare", 60000, "A", "2026-01-01")])
    assert (out["owed_by"], out["amount_minor"], out["due_on"]) == ("A", 30000, "2026-10-15")
    assert E.evaluate(rs, ok, exp("school_supplies", 4000))["reason"] == "not_shared"


FEE_PAYER = {"id": "R90", "origin": "resolution", "kind": "fee_policy", "category": "*", "params": {"payer_adds": True},
             "source": {"question_id": "q_fee", "answered_by": ["A", "B"], "answered_at": "2026-10-01T00:00:00+00:00"}}


def test_fee_resolution_adds_estimate():
    rs, ok = approved(PLAN1, [FEE_PAYER])
    d = E.evaluate(rs, ok, exp("medical", 42000))
    assert d["amount_minor"] == 26128 and {"fee_added_estimate": 928} in d["notes"] and {"resolution": "R90"} in d["cite"]


def test_receiver_bears_fee_changes_nothing():
    rs, ok = approved(PLAN1, [{**FEE_PAYER, "params": {"payer_adds": False}}])
    assert E.evaluate(rs, ok, exp("medical", 42000))["amount_minor"] == 25200
