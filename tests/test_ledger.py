"""The ledger feed behind Money & Time: one family's authorised rows, nothing private, nothing from other families."""
import json
from datetime import date, timedelta

import sqlalchemy as sa
from fastapi.testclient import TestClient

from between import db, ruleset as RS
from between.engine import annual_cap_used
from webutil import make, submit_expense

TEST_ACTOR = {"kind": "system", "role": None, "session_ref": "test"}


def approved_demo(app=None, engine=None):
    if app is None:
        app, engine = make(demo_parent_a_email="sb-a@personal.example.com", demo_parent_b_email="sb-b@personal.example.com")
    c = TestClient(app)
    fid = c.post("/demo/new", follow_redirects=False).headers["location"].rsplit("/", 1)[1]
    with engine.begin() as conn:
        row = conn.execute(sa.select(db.ruleset).where(db.ruleset.c.family_id == fid)).mappings().first()
        for role in ("A", "B"):
            RS.approve(conn, row["id"], role, row["hash"], TEST_ACTOR)
    return app, engine, c, fid


def test_cap_used_matches_engine():
    h = [{"category": "extracurricular", "year": 2026, "amount_minor": 30000, "paid_by": "A", "owed_by": "B", "owed_minor": 15000},
         {"category": "extracurricular", "year": 2026, "amount_minor": 30000, "paid_by": "B", "owed_by": "A", "owed_minor": 15000}]
    # B owed 15000 on the first and carried 30000 - 15000 of the second himself
    assert annual_cap_used(h, "extracurricular", 2026, "B") == 30000
    assert annual_cap_used(h, "extracurricular", 2025, "B") == 0


def test_feed_scoped_to_family():
    app, engine, c1, fid1 = approved_demo()
    _, _, c2, fid2 = approved_demo(app, engine)
    assert submit_expense(c1, fid1, "medical", amount="420.00").status_code == 303
    assert submit_expense(c2, fid2, "medical", receipt=b"\x89PNG other receipt", amount="100.00").status_code == 303
    feed = c1.get(f"/f/{fid1}/money.json").json()
    other_ids = {r[0] for r in engine.connect().execute(sa.select(db.expense.c.id).where(db.expense.c.family_id == fid2))}
    assert other_ids and not any(i in json.dumps(feed) for i in other_ids)
    assert c1.get(f"/f/{fid2}/money.json").status_code == 403


def test_feed_has_no_private_keys():
    app, engine, c, fid = approved_demo()
    submit_expense(c, fid, "medical", amount="420.00")
    text = c.get(f"/f/{fid}/money.json").text
    for bad in ('"answer', '"note"', '"text"', "paypal_email", "sb-a@", "sb-b@"):
        assert bad not in text, bad


def test_pay_window_from_decision():
    app, engine, c, fid = approved_demo()
    submit_expense(c, fid, "medical", amount="420.00")
    feed = c.get(f"/f/{fid}/money.json").json()
    [w] = [o for o in feed["obligations"] if o["kind"] == "pay-window"]
    start = date.fromisoformat(w["start"])
    assert date.fromisoformat(w["end"]) == start + timedelta(days=14)
    assert (w["amountMinor"], w["owedBy"], w["owedTo"], w["state"]) == (25200, "B", "A", "open")
    assert "7.2" in w["clause"]
    [e] = feed["expenses"]
    assert e["amountMinor"] == 42000 and e["amount"] == 420.0 and e["paidBy"] == "A"
    assert {cl["section"] for cl in feed["clauses"]} >= {"6.1", "7.2"}
    assert all(cl["quote"] for cl in feed["clauses"])


def test_cap_row_for_activities():
    app, engine, c, fid = approved_demo()
    caps = c.get(f"/f/{fid}/money.json").json()["caps"]
    by_party = {r["party"]: r for r in caps if r["category"] == "extracurricular"}
    assert set(by_party) == {"A", "B"}
    assert by_party["A"]["cap"] == 1500.0 and by_party["A"]["left"] == 1500.0 and by_party["A"]["used"] == 0.0
    assert "6.3" in by_party["B"]["clause"]


def test_caps_empty_until_both_approve():
    app, engine = make()
    c = TestClient(app)
    fid = c.post("/demo/new", follow_redirects=False).headers["location"].rsplit("/", 1)[1]
    assert c.get(f"/f/{fid}/money.json").json()["caps"] == []
