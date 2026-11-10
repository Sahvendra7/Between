import copy
from datetime import timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

from between import db, engine as E, ruleset as RS, validate as V
from conftest import insert_family
from keys import PLAN1, PLAN3

DOCS = Path(__file__).parent.parent / "samples" / "agreements"
A = {"kind": "parent", "role": "A", "session_ref": "aaaa0000"}
B = {"kind": "parent", "role": "B", "session_ref": "bbbb0000"}

ITEM3 = {"kind": "split", "category": "medical", "params": {"shares": {"A": 30, "B": 70}},
         "source": {"quote": "Dad pays 70%, Mom pays 30%.", "page": 1, "section": "Item 3"}}
APPX = {"kind": "split", "category": "medical", "params": {"shares": {"A": 50, "B": 50}},
        "source": {"quote": "All medical costs will be split equally between Mom and Dad.", "page": 3, "section": "A.1"}}


def setup(conn, now, key=PLAN1, extra=()):
    insert_family(conn)
    text = (DOCS / key["doc"]).read_text()
    conn.execute(sa.insert(db.agreement).values(id="ag1", family_id="f1", sha256="x", text=text, uploaded_by="A", uploaded_at=now))
    raw = {"rules": copy.deepcopy(key["rules"]) + [copy.deepcopy(r) for r in extra], "ambiguities": copy.deepcopy(key["ambiguities"])}
    v = V.validate(raw, text, key["parties"])
    return RS.create_version(conn, "f1", "ag1", v, key["parties"], A, now=now)


def expense(cat="medical", cents=10000):
    return {"id": "e1", "category": cat, "amount_minor": cents, "paid_by": "A", "incurred_on": "2026-10-01",
            "requested_on": "2026-10-02", "receipt": True}


def test_engine_refuses_until_both_approve(conn, now):
    v1 = setup(conn, now)
    RS.approve(conn, v1["id"], "A", v1["hash"], A, now=now)
    rs, approvals = RS.current(conn, "f1")
    assert set(approvals) == {"A"} and E.evaluate(rs, approvals, expense())["status"] == "refused"
    RS.approve(conn, v1["id"], "B", v1["hash"], B, now=now)
    rs, approvals = RS.current(conn, "f1")
    assert E.evaluate(rs, approvals, expense())["status"] == "payable"


def test_stale_hash_approval_rejected(conn, now):
    v1 = setup(conn, now)
    with pytest.raises(RS.RulesetError) as e:
        RS.approve(conn, v1["id"], "A", "0" * 64, A, now=now)
    assert e.value.code == "stale_version"


def test_new_version_resets_approvals(conn, now):
    v1 = setup(conn, now, PLAN3, extra=[ITEM3, APPX])
    RS.approve(conn, v1["id"], "A", v1["hash"], A, now=now)
    q = next(q for q in v1["json"]["questions"] if q["type"] == "contradiction")
    RS.submit_answer(conn, v1["id"], q["id"], "A", "use_0", None, A, now=now)
    RS.submit_answer(conn, v1["id"], q["id"], "B", "use_0", None, B, now=now)
    v2 = RS.resolve_if_agreed(conn, "f1", v1["id"], A, now=now)
    assert v2["version"] == 2 and RS.current(conn, "f1")[1] == {}
    with pytest.raises(RS.RulesetError) as e:
        RS.approve(conn, v1["id"], "B", v1["hash"], B, now=now)
    assert e.value.code == "not_latest"


def test_other_answer_hidden_until_both_answered(conn, now):
    v1 = setup(conn, now, PLAN3, extra=[ITEM3, APPX])
    q = v1["json"]["questions"][0]
    RS.submit_answer(conn, v1["id"], q["id"], "A", "use_1", None, A, now=now)
    seen_by_b = RS.answers_for(conn, v1["id"], q["id"], "B")
    assert seen_by_b == {"mine": None, "other": None, "both_answered": False}
    assert RS.answers_for(conn, v1["id"], q["id"], "A")["mine"]["choice"] == "use_1"
    RS.submit_answer(conn, v1["id"], q["id"], "B", "use_0", None, B, now=now)
    assert RS.answers_for(conn, v1["id"], q["id"], "B")["other"]["choice"] == "use_1"


def test_matching_answers_create_resolution_version(conn, now):
    v1 = setup(conn, now, PLAN3, extra=[ITEM3, APPX])
    q = v1["json"]["questions"][0]
    use_item3 = next(o["choice"] for o in RS.options_for(q, v1["json"]["rules"])
                     if o["makes_rule"] and o["makes_rule"]["params"]["shares"] == {"A": 30, "B": 70})
    for role, actor in (("A", A), ("B", B)):
        RS.submit_answer(conn, v1["id"], q["id"], role, use_item3, None, actor, now=now)
    v2 = RS.resolve_if_agreed(conn, "f1", v1["id"], A, now=now)
    res = [r for r in v2["json"]["rules"] if r["origin"] == "resolution"]
    assert len(res) == 1 and res[0]["id"] == "R1" and res[0]["source"]["question_id"] == q["id"]
    assert res[0]["source"]["answered_by"] == ["A", "B"]
    for role, actor in (("A", A), ("B", B)):
        RS.approve(conn, v2["id"], role, v2["hash"], actor, now=now)
    rs, approvals = RS.current(conn, "f1")
    out = E.evaluate(rs, approvals, expense())
    assert (out["status"], out["amount_minor"], out["cite"][0]) == ("payable", 7000, {"resolution": "R1"})


def test_differing_answers_keep_question_open(conn, now):
    v1 = setup(conn, now, PLAN3, extra=[ITEM3, APPX])
    q = v1["json"]["questions"][0]
    RS.submit_answer(conn, v1["id"], q["id"], "A", "use_0", None, A, now=now)
    RS.submit_answer(conn, v1["id"], q["id"], "B", "use_1", None, B, now=now)
    assert RS.resolve_if_agreed(conn, "f1", v1["id"], A, now=now) is None
    for role, actor in (("A", A), ("B", B)):
        RS.approve(conn, v1["id"], role, v1["hash"], actor, now=now)
    rs, approvals = RS.current(conn, "f1")
    assert E.evaluate(rs, approvals, expense())["status"] == "needs_parents"


def test_decide_together_creates_no_rule(conn, now):
    v1 = setup(conn, now, PLAN3, extra=[ITEM3, APPX])
    q = v1["json"]["questions"][0]
    for role, actor in (("A", A), ("B", B)):
        RS.submit_answer(conn, v1["id"], q["id"], role, "together", None, actor, now=now)
    assert RS.resolve_if_agreed(conn, "f1", v1["id"], A, now=now) is None


def test_answers_locked_after_both(conn, now):
    v1 = setup(conn, now, PLAN3, extra=[ITEM3, APPX])
    q = v1["json"]["questions"][0]
    RS.submit_answer(conn, v1["id"], q["id"], "A", "use_0", None, A, now=now)
    RS.submit_answer(conn, v1["id"], q["id"], "A", "use_1", None, A, now=now)  # can change before B answers
    RS.submit_answer(conn, v1["id"], q["id"], "B", "use_1", None, B, now=now)
    with pytest.raises(RS.RulesetError) as e:
        RS.submit_answer(conn, v1["id"], q["id"], "A", "use_0", None, A, now=now)
    assert e.value.code == "locked"


def test_unknown_choice_refused(conn, now):
    v1 = setup(conn, now, PLAN3, extra=[ITEM3, APPX])
    with pytest.raises(RS.RulesetError) as e:
        RS.submit_answer(conn, v1["id"], v1["json"]["questions"][0]["id"], "A", "father_pays_all", None, A, now=now)
    assert e.value.code == "bad_choice"


def test_missing_number_needs_matching_values(conn, now):
    from keys import PLAN2
    v1 = setup(conn, now, PLAN2)
    q = next(q for q in v1["json"]["questions"] if q["type"] == "missing_number")
    RS.submit_answer(conn, v1["id"], q["id"], "A", "days", "30", A, now=now)
    RS.submit_answer(conn, v1["id"], q["id"], "B", "days", "45", B, now=now)
    assert RS.resolve_if_agreed(conn, "f1", v1["id"], A, now=now) is None
    with pytest.raises(RS.RulesetError):
        RS.submit_answer(conn, v1["id"], q["id"], "A", "days", "0", A, now=now)


def test_events_record_versions_and_approvals(conn, now):
    from between import record
    v1 = setup(conn, now)
    RS.approve(conn, v1["id"], "A", v1["hash"], A, now=now)
    types = [e["type"] for e in record.events(conn, "f1")]
    assert types == ["ruleset.created", "ruleset.approved"] and record.check(conn, "f1") is None
