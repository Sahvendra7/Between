"""Money & Time routes: the demo sample year, and history settled outside Between that is never PayPal-verified."""
import json
import re

import sqlalchemy as sa
from fastapi.testclient import TestClient

from between import db
from test_ledger import approved_demo
from webutil import FakePayPal, csrf, make, two_parents


def add_year(c, fid):
    return c.post(f"/f/{fid}/money/sample-year", data={"csrf": csrf(c.get(f"/f/{fid}/expenses/new").text)},
                  follow_redirects=False)


def switch(c, fid):
    assert c.post(f"/demo/switch/{fid}", data={"csrf": csrf(c.get(f"/f/{fid}").text)}, follow_redirects=False).status_code == 303


def decisions(engine, fid):
    with engine.connect() as conn:
        return [json.loads(r.json) | {"expense_id": r.expense_id, "category": r.category} for r in conn.execute(
            sa.select(db.decision.c.json, db.decision.c.expense_id, db.expense.c.category)
            .join(db.expense, db.expense.c.id == db.decision.c.expense_id).where(db.expense.c.family_id == fid))]


def test_sample_year_requires_demo_and_approval():
    app, engine = make()
    a, b, fid = two_parents(app)
    assert add_year(a, fid).status_code == 403
    c = TestClient(app)
    demo_fid = c.post("/demo/new", follow_redirects=False).headers["location"].rsplit("/", 1)[1]
    assert add_year(c, demo_fid).status_code == 409


def test_sample_year_adds_twelve_and_is_once_only():
    app, engine, c, fid = approved_demo()
    r = add_year(c, fid)
    assert r.status_code == 303 and r.headers["location"] == f"/f/{fid}/money"
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(db.expense).where(db.expense.c.family_id == fid)).scalar() == 12
    assert add_year(c, fid).status_code == 409
    switch(c, fid)
    assert add_year(c, fid).status_code == 409


def test_sample_year_outcomes_come_from_engine():
    app, engine, c, fid = approved_demo()
    add_year(c, fid)
    ds = decisions(engine, fid)
    statuses = {(d["status"], d.get("reason")) for d in ds}
    assert {("needs_consent", "prior_consent_missing"), ("rejected", "requested_too_late"), ("rejected", "not_shared")} <= statuses
    assert sum(d["status"] == "payable" for d in ds) == 9
    with engine.connect() as conn:
        pays = conn.execute(sa.select(db.payment.c.status, db.payment.c.verification)).all()
    assert len(pays) == 8 and all(p == ("outside", "not_applicable") for p in pays)


def test_outside_payment_not_payable_and_labelled():
    pp = FakePayPal()
    app, engine = make(pp=pp, demo_parent_a_email="sb-a@personal.example.com", demo_parent_b_email="sb-b@personal.example.com")
    app, engine, c, fid = approved_demo(app, engine)
    add_year(c, fid)
    with engine.connect() as conn:
        eid = conn.execute(sa.select(db.payment.c.expense_id).join(db.expense, db.expense.c.id == db.payment.c.expense_id)
                           .where(db.expense.c.paid_by == "A", db.payment.c.status == "outside")).scalars().first()
    switch(c, fid)  # Father owes on Mother's expenses
    loc = f"/f/{fid}/expenses/{eid}"
    page = c.get(loc).text
    assert "Settled outside Between · not verified by PayPal" in page and "Pay $" not in page
    pay_page = c.get(loc + "/pay").text
    h = re.search(r'name="decision_hash" value="([0-9a-f]{64})"', pay_page).group(1)
    r = c.post(loc + "/pay", data={"csrf": csrf(pay_page), "confirm": "yes", "decision_hash": h}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == loc
    assert not [x for x in pp.calls if x[0] == "create"]
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(db.payment).where(db.payment.c.expense_id == eid)).scalar() == 1


def test_record_verify_skips_outside():
    pp = FakePayPal()
    app, engine = make(pp=pp)
    app, engine, c, fid = approved_demo(app, engine)
    add_year(c, fid)
    r = c.post(f"/f/{fid}/record/verify", data={"csrf": csrf(c.get(f"/f/{fid}/record").text)}, follow_redirects=False)
    assert r.status_code == 303 and pp.calls == []


def test_balance_counts_outside_separately():
    app, engine, c, fid = approved_demo()
    add_year(c, fid)
    home = c.get(f"/f/{fid}").text
    assert "Settled outside Between (not verified)" in home


AG_STUDIO_SRC = "https://cdn.jsdelivr.net/npm/ag-studio@3.1.0/dist/umd/ag-studio.min.js"
AG_STUDIO_SRI = "sha384-AQulWK/PF30iLAso56dIH/1+Iv852aUbFC98K7N1ZpLYVvmamIEAU36dEbUaPym1"


def test_money_page_csp_scoped():
    from between.web.app import CSP
    from between.web.routes_money import MONEY_CSP
    app, engine, c, fid = approved_demo()
    r = c.get(f"/f/{fid}/money")
    assert r.status_code == 200 and r.headers["content-security-policy"] == MONEY_CSP
    assert "style-src 'self' 'unsafe-inline'" in MONEY_CSP and "script-src 'self' https://cdn.jsdelivr.net;" in MONEY_CSP
    assert f'src="{AG_STUDIO_SRC}"' in r.text and f'integrity="{AG_STUDIO_SRI}"' in r.text and 'crossorigin="anonymous"' in r.text
    for path in (f"/f/{fid}", f"/f/{fid}/calendar", f"/f/{fid}/money.json"):
        assert c.get(path).headers["content-security-policy"] == CSP, path


def test_money_page_fallback_lists_expenses():
    app, engine, c, fid = approved_demo()
    add_year(c, fid)
    page = c.get(f"/f/{fid}/money").text
    assert 'id="ledger-fallback"' in page
    for amount in ("$180.00", "$240.00", "$600.00", "$330.00"):
        assert amount in page, amount
    assert "Settled outside Between · not verified by PayPal" in page


def test_money_page_offers_sample_year_only_when_empty():
    app, engine, c, fid = approved_demo()
    assert "Add a sample year (synthetic)" in c.get(f"/f/{fid}/money").text
    add_year(c, fid)
    assert "Add a sample year (synthetic)" not in c.get(f"/f/{fid}/money").text


def test_money_page_without_approved_rules():
    app, engine = make()
    c = TestClient(app)
    fid = c.post("/demo/new", follow_redirects=False).headers["location"].rsplit("/", 1)[1]
    r = c.get(f"/f/{fid}/money")
    assert r.status_code == 200 and "Approve your rules to see your year." in r.text


def test_money_page_other_family_403():
    app, engine, c1, fid1 = approved_demo()
    _, _, c2, fid2 = approved_demo(app, engine)
    assert c1.get(f"/f/{fid2}/money").status_code == 403


def test_nav_links_money_and_time():
    app, engine, c, fid = approved_demo()
    assert f'href="/f/{fid}/money">Money &amp; Time</a>' in c.get(f"/f/{fid}").text


def counts_all(engine):
    with engine.connect() as conn:
        return {t.name: conn.execute(sa.select(sa.func.count()).select_from(t)).scalar()
                for t in (db.expense, db.decision, db.consent, db.payment, db.event)}


def preview(c, fid, body, token=True, token_fid=None):
    headers = {"X-CSRF-Token": csrf(c.get(f"/f/{token_fid or fid}/expenses/new").text)} if token else {}
    return c.post(f"/f/{fid}/money/preview", json=body, headers=headers)


def test_money_json_has_pay_windows_and_custody():
    app, engine, c, fid = approved_demo()
    add_year(c, fid)
    cal = c.get(f"/f/{fid}/money.json").json()["calendar"]
    kinds = {e["kind"] for e in cal["events"]}
    assert {"custody", "expense", "pay-window"} <= kinds and {r["id"] for r in cal["resources"]} == {"A", "B"}
    [w] = [e for e in cal["events"] if e["kind"] == "pay-window" and e["state"] == "open"]
    assert w["resourceId"] == "B" and "§7.2" in w["name"] and w["expenseId"]


def test_preview_needs_consent_and_writes_nothing():
    app, engine, c, fid = approved_demo()
    before = counts_all(engine)
    r = preview(c, fid, {"category": "extracurricular", "amountMinor": 45000, "incurredOn": "2026-12-14", "paidBy": "A"})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "needs_consent" and d["cite"][0]["section"] == "6.2" and d["cite"][0]["quote"]
    assert counts_all(engine) == before


def test_preview_medical_share():
    app, engine, c, fid = approved_demo()
    d = preview(c, fid, {"category": "medical", "amountMinor": 42000, "incurredOn": "2026-11-12", "paidBy": "A"}).json()
    assert (d["status"], d["owedBy"], d["owedTo"], d["amountMinor"]) == ("payable", "B", "A", 25200)
    assert d["dueOn"] == "2026-11-26" and {x["section"] for x in d["cite"]} >= {"6.1", "7.2"}


def test_preview_rejects_bad_input_and_csrf():
    app, engine, c, fid = approved_demo()
    good = {"category": "medical", "amountMinor": 1000, "incurredOn": "2026-11-12", "paidBy": "A"}
    for bad in ({**good, "category": "rent"}, {**good, "amountMinor": 0}, {**good, "amountMinor": "10"},
                {**good, "incurredOn": "12/11/2026"}, {**good, "paidBy": "C"}):
        assert preview(c, fid, bad).status_code == 400, bad
    assert preview(c, fid, good, token=False).status_code == 403
    _, _, c2, fid2 = approved_demo(app, engine)
    assert preview(c2, fid, good, token_fid=fid2).status_code == 403
