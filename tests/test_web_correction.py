import re
from pathlib import Path

import sqlalchemy as sa

from between import db
from keys import PLAN1
from webutil import FakePayPal, csrf, fake_ai, family_with_rules, make, submit_expense

DOC1 = (Path(__file__).parent.parent / "samples" / "agreements" / PLAN1["doc"]).read_text()


def paid(pp=None):
    pp = pp or FakePayPal()
    app, engine = make(ai=fake_ai(PLAN1), pp=pp)
    a, b, fid = family_with_rules(app, DOC1)
    loc = submit_expense(a, fid, "medical").headers["location"]
    page = b.get(loc + "/pay").text
    h = re.search(r'name="decision_hash" value="([0-9a-f]{64})"', page).group(1)
    r = b.post(loc + "/pay", data={"csrf": csrf(page), "confirm": "yes", "decision_hash": h}, follow_redirects=False)
    b.get("/pay/return?p=" + re.search(r"token=O-pay_([0-9a-f]+)", r.headers["location"]).group(1))
    return app, engine, pp, a, b, fid, loc


def amend(client, loc, amount):
    page = client.get(loc.rsplit("/expenses/", 1)[0] + "/expenses/new").text  # every parent's page with a form
    return client.post(loc + "/amend", data={"csrf": csrf(page), "amount": amount}, follow_redirects=False)


def test_amend_after_payment_creates_return_card():
    app, engine, pp, a, b, fid, loc = paid()
    assert amend(a, loc, "380.00").status_code == 303
    card = a.get(loc).text
    assert "Return $24.00 to Father" in card and "refund" not in card.lower()
    assert "Return $24.00" not in b.get(loc).text  # only the parent who received too much returns it


def test_return_flows_like_a_payment_and_is_verified():
    app, engine, pp, a, b, fid, loc = paid()
    amend(a, loc, "380.00")
    page = a.get(loc + "/return").text
    assert "PayPal sandbox checkout" in page and "about $1.33 (estimate)" in page
    r = a.post(loc + "/return", data={"csrf": csrf(page), "confirm": "yes"}, follow_redirects=False)
    assert r.status_code == 303 and "sandbox.paypal.com" in r.headers["location"]
    order = pp.orders[re.search(r"token=(O-pay_[0-9a-f]+)", r.headers["location"]).group(1)]
    assert (order["amount"], order["payee"], order["custom_id"][:5]) == (2400, "sb-father@personal.example.com", "corr_")
    a.get("/pay/return?p=" + re.search(r"token=O-pay_([0-9a-f]+)", r.headers["location"]).group(1))
    with engine.connect() as c:
        corr = c.execute(sa.select(db.payment).where(db.payment.c.kind == "correction")).mappings().one()
    assert (corr["status"], corr["verification"], corr["payer_role"], corr["payee_role"]) == ("completed", "verified", "A", "B")
    assert "Returned · verified with PayPal" in a.get(loc).text


def test_only_paying_parent_amends_and_only_decreases():
    app, engine, pp, a, b, fid, loc = paid()
    assert amend(b, loc, "380.00").status_code == 403
    assert amend(a, loc, "500.00").status_code == 409
    assert amend(a, loc, "abc").status_code == 400


def test_amend_before_payment_just_redecides():
    pp = FakePayPal()
    app, engine = make(ai=fake_ai(PLAN1), pp=pp)
    a, b, fid = family_with_rules(app, DOC1)
    loc = submit_expense(a, fid, "medical").headers["location"]
    assert amend(a, loc, "380.00").status_code == 303
    card = a.get(loc).text
    assert "$228.00" in card and "Return" not in card


def test_cancelled_return_stays_owed():
    app, engine, pp, a, b, fid, loc = paid()
    amend(a, loc, "380.00")
    page = a.get(loc + "/return").text
    r = a.post(loc + "/return", data={"csrf": csrf(page), "confirm": "yes"}, follow_redirects=False)
    a.get("/pay/cancel?p=" + re.search(r"token=O-pay_([0-9a-f]+)", r.headers["location"]).group(1))
    with engine.connect() as c:
        assert c.execute(sa.select(db.payment.c.status).where(db.payment.c.kind == "correction")).scalar_one() == "due"
    assert "Return $24.00 to Father" in a.get(loc).text
