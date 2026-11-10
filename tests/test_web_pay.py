import re
from pathlib import Path
from urllib.parse import urlparse

import sqlalchemy as sa

from between import db, record
from keys import PLAN1
from webutil import FakePayPal, csrf, fake_ai, family_with_rules, make, submit_expense

DOC1 = (Path(__file__).parent.parent / "samples" / "agreements" / PLAN1["doc"]).read_text()


def setup(capture_status="COMPLETED"):
    pp = FakePayPal(capture_status)
    app, engine = make(ai=fake_ai(PLAN1), pp=pp)
    a, b, fid = family_with_rules(app, DOC1)  # a = Mother, b = Father
    loc = submit_expense(a, fid, "medical").headers["location"]  # Mother paid $420; Father owes $252
    return app, engine, pp, a, b, fid, loc


def pay(client, loc, confirm="yes", decision_hash=None):
    page = client.get(loc + "/pay").text
    h = decision_hash or re.search(r'name="decision_hash" value="([0-9a-f]{64})"', page).group(1)
    return client.post(loc + "/pay", data={"csrf": csrf(page), "confirm": confirm, "decision_hash": h}, follow_redirects=False)


def back_from_paypal(client, resp):
    q = urlparse(resp.headers["location"]).query  # PayPal would redirect to return_url; we follow it directly
    pid = re.search(r"token=O-pay_([0-9a-f]+)", "?" + q).group(1)
    return client.get(f"/pay/return?p={pid}&token=O-pay_{pid}")


def payments(engine):
    with engine.connect() as c:
        return [dict(r) for r in c.execute(sa.select(db.payment)).mappings()]


def test_only_owing_parent_can_pay():
    app, engine, pp, a, b, fid, loc = setup()
    assert a.get(loc + "/pay").status_code == 403
    assert "Pay $252.00 with PayPal" in b.get(loc).text and "Pay $252.00" not in a.get(loc).text


def test_pay_requires_confirm_and_current_decision_hash():
    app, engine, pp, a, b, fid, loc = setup()
    assert pay(b, loc, confirm="").status_code == 400
    assert pay(b, loc, decision_hash="0" * 64).status_code == 409
    assert payments(engine) == [] and pp.calls == []


def test_redirects_to_paypal_sandbox_with_payee_and_amount():
    app, engine, pp, a, b, fid, loc = setup()
    r = pay(b, loc)
    assert r.status_code == 303 and r.headers["location"].startswith("https://www.sandbox.paypal.com/checkoutnow?token=")
    order = next(iter(pp.orders.values()))
    assert (order["amount"], order["payee"]) == (25200, "sb-mother@personal.example.com")


def test_double_submit_creates_one_order():
    app, engine, pp, a, b, fid, loc = setup()
    pay(b, loc); pay(b, loc)
    assert len(pp.orders) == 1 and len(payments(engine)) == 1
    assert len({rid for kind, rid in pp.calls if kind == "create"}) == 1


def test_return_twice_captures_once():
    app, engine, pp, a, b, fid, loc = setup()
    r = pay(b, loc)
    assert back_from_paypal(b, r).status_code == 200
    again = back_from_paypal(b, r)
    assert again.status_code == 200 and "Verified with PayPal" in again.text
    with engine.connect() as c:
        changes = [e for e in record.events(c, fid) if e["type"] == "payment.status_changed" and e["body"]["to"] == "completed"]
    assert len(changes) == 1 and sum(1 for k, _ in pp.calls if k == "capture") == 2


def test_payment_counts_only_after_verify():
    app, engine, pp, a, b, fid, loc = setup()
    r = pay(b, loc)
    assert "Paid · verified with PayPal" not in a.get(loc).text
    back_from_paypal(b, r)
    assert "Paid · verified with PayPal" in a.get(loc).text
    p = payments(engine)[0]
    assert (p["status"], p["verification"], p["gross_minor"], p["fee_minor"], p["net_minor"]) == ("completed", "verified", 25200, 928, 24272)


def test_fee_shown_as_estimate_then_actual():
    app, engine, pp, a, b, fid, loc = setup()
    page = b.get(loc + "/pay").text
    assert "PayPal sandbox checkout" in page and "about $9.28 (estimate)" in page and "Friends &amp; Family" in page
    result = back_from_paypal(b, pay(b, loc)).text
    assert "from PayPal" in result and "$9.28" in result and "$242.72" in result


def test_cancel_marks_cancelled_and_allows_retry():
    app, engine, pp, a, b, fid, loc = setup()
    r = pay(b, loc)
    pid = re.search(r"token=O-pay_([0-9a-f]+)", r.headers["location"]).group(1)
    assert b.get(f"/pay/cancel?p={pid}", follow_redirects=False).status_code == 303
    assert payments(engine)[0]["status"] == "cancelled"
    assert pay(b, loc).status_code == 303 and len(payments(engine)) == 2


def test_other_parent_cannot_use_return_link():
    app, engine, pp, a, b, fid, loc = setup()
    r = pay(b, loc)
    pid = re.search(r"token=O-pay_([0-9a-f]+)", r.headers["location"]).group(1)
    assert a.get(f"/pay/return?p={pid}").status_code == 403


def webhook(client, event_id, capture_id, order_id, event_type="PAYMENT.CAPTURE.COMPLETED"):
    event = {"id": event_id, "event_type": event_type,
             "resource": {"id": capture_id, "status": "COMPLETED", "supplementary_data": {"related_ids": {"order_id": order_id}}}}
    return client.post("/webhooks/paypal", json=event, headers={"paypal-transmission-id": "t", "paypal-transmission-sig": "s"})


def test_webhook_bad_signature_400_and_ignored():
    app, engine, pp, a, b, fid, loc = setup()
    pp.webhook_ok = False
    assert webhook(b, "WH-1", "C-x", "O-x").status_code == 400
    with engine.connect() as c:
        assert c.execute(sa.select(sa.func.count()).select_from(db.webhook_event)).scalar() == 0


def test_webhook_duplicate_event_ignored():
    app, engine, pp, a, b, fid, loc = setup()
    r = pay(b, loc)
    oid = next(iter(pp.orders))
    pp.orders[oid]["captured"] = True  # captured on PayPal's side; Between hasn't seen the return yet
    assert webhook(b, "WH-1", "C-" + oid, oid).status_code == 200
    n = len(pp.calls)
    assert webhook(b, "WH-1", "C-" + oid, oid).status_code == 200 and len(pp.calls) == n


def test_webhook_triggers_get_capture_not_direct_status():
    app, engine, pp, a, b, fid, loc = setup(capture_status="PENDING")
    pay(b, loc)
    oid = next(iter(pp.orders))
    pp.orders[oid]["captured"] = True
    webhook(b, "WH-2", "C-" + oid, oid)  # the event says COMPLETED; PayPal's GET says PENDING
    p = payments(engine)[0]
    assert p["status"] == "pending" and p["verification"] == "verified"


def test_record_check_completes_an_approved_but_abandoned_checkout():
    app, engine, pp, a, b, fid, loc = setup()
    pay(b, loc)  # the payer approves on PayPal but never comes back to Between
    page = b.get(f"/f/{fid}/record").text
    b.post(f"/f/{fid}/record/verify", data={"csrf": csrf(page)})
    p = payments(engine)[0]
    assert (p["status"], p["verification"]) == ("completed", "verified")
    assert [rid for k, rid in pp.calls if k == "capture"] == [f"pay_{p['id']}_capture"]


def test_order_approved_webhook_completes_capture_once():
    app, engine, pp, a, b, fid, loc = setup()
    pay(b, loc)
    oid = next(iter(pp.orders))
    approved = {"id": "WH-A", "event_type": "CHECKOUT.ORDER.APPROVED", "resource": {"id": oid, "status": "APPROVED"}}
    assert b.post("/webhooks/paypal", json=approved).status_code == 200
    assert b.post("/webhooks/paypal", json={**approved, "id": "WH-B"}).status_code == 200
    assert payments(engine)[0]["status"] == "completed" and sum(1 for k, _ in pp.calls if k == "capture") == 1  # 2nd sees the recorded capture


def test_unconfirmed_payment_is_never_captured_by_the_server():
    app, engine, pp, a, b, fid, loc = setup()
    pay(b, loc)
    with engine.begin() as c:
        c.execute(sa.update(db.payment).values(status="cancelled"))
    page = b.get(f"/f/{fid}/record").text
    b.post(f"/f/{fid}/record/verify", data={"csrf": csrf(page)})
    assert not any(k == "capture" for k, _ in pp.calls)
