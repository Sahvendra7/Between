"""JSON mode for the Next.js frontend: same context as the HTML page, and allowlisted frontend origins for links."""
from fastapi.testclient import TestClient

from keys import PLAN1
from test_web_pay import DOC1, pay
from webutil import FakePayPal, fake_ai, family_with_rules, make, submit_expense

J = {"x-between-json": "1"}
FRONT = "https://between.example.vercel.app"


def test_page_returns_its_template_context_as_json():
    app, _ = make(ai=fake_ai(PLAN1), pp=FakePayPal(), frontend_origins=(FRONT,))
    a, b, fid = family_with_rules(app, DOC1)
    home = a.get(f"/f/{fid}", headers=J).json()
    assert home["template"] == "home" and home["ctx"]["s"]["role"] == "A" and home["ctx"]["s"]["csrf"]
    rules = a.get(f"/f/{fid}/rules", headers=J).json()["ctx"]
    assert all(r["text"] for r in rules["agreement_rules"])  # wording comes from present.describe_rule, not the frontend
    assert a.get(f"/f/{fid}").headers["content-type"].startswith("text/html")  # the Render UI is unchanged


def test_errors_are_json_and_other_families_stay_closed():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = family_with_rules(app, DOC1)
    r = TestClient(app).get(f"/f/{fid}", headers=J)
    assert r.status_code == 403 and r.json()["template"] == "error" and "csrf" not in r.text


def test_paypal_return_url_follows_only_allowlisted_frontend():
    pp = FakePayPal()
    calls = []
    orig = pp.create_order
    pp.create_order = lambda *a: calls.append(a[4]) or orig(*a)
    app, _ = make(ai=fake_ai(PLAN1), pp=pp, frontend_origins=(FRONT,))
    a, b, fid = family_with_rules(app, DOC1)
    loc = submit_expense(a, fid, "medical").headers["location"]
    b.headers.update({"x-between-origin": "https://evil.example"})
    assert pay(b, loc).status_code == 303 and calls[-1].startswith("http://testserver/pay/return")
    pp.orders.clear()
    b.headers.update({"x-between-origin": FRONT})
    page = b.get(loc + "/pay").text
    import re
    h = re.search(r'name="decision_hash" value="([0-9a-f]{64})"', page).group(1)
    from webutil import csrf
    b.post(loc + "/pay", data={"csrf": csrf(page), "confirm": "yes", "decision_hash": h}, follow_redirects=False)
    assert calls[-1].startswith(FRONT + "/pay/return")


def test_envelope_names_the_signed_in_parent():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = family_with_rules(app, DOC1)
    v = b.get(f"/f/{fid}/expenses/new", headers=J).json()["viewer"]
    assert v == {"fid": fid, "role": "B", "names": {"A": "Mother", "B": "Father"}, "me": "David"}
    assert TestClient(app).get("/join/nope", headers=J).json()["viewer"] is None
