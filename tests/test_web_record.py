import importlib.util
import re
from pathlib import Path

import sqlalchemy as sa

from between import db
from keys import PLAN1
from webutil import FakePayPal, csrf, fake_ai, family_with_rules, make, submit_expense

ROOT = Path(__file__).parent.parent
DOC1 = (ROOT / "samples" / "agreements" / PLAN1["doc"]).read_text()


def paid_family(tmp_path=None):
    pp = FakePayPal()
    app, engine = make(ai=fake_ai(PLAN1), pp=pp)
    a, b, fid = family_with_rules(app, DOC1)
    loc = submit_expense(a, fid, "medical").headers["location"]
    page = b.get(loc + "/pay").text
    h = re.search(r'name="decision_hash" value="([0-9a-f]{64})"', page).group(1)
    r = b.post(loc + "/pay", data={"csrf": csrf(page), "confirm": "yes", "decision_hash": h}, follow_redirects=False)
    pid = re.search(r"token=O-pay_([0-9a-f]+)", r.headers["location"]).group(1)
    b.get(f"/pay/return?p={pid}")
    return app, engine, pp, a, b, fid


def test_record_shows_actor_and_chain_ok():
    app, engine, pp, a, b, fid = paid_family()
    page = a.get(f"/f/{fid}/record").text
    assert "Record intact" in page and "Mother" in page and "Father" in page
    assert "payment.status_changed" in page and "completed" in page and "$242.72" in page


def test_record_flags_tampered_chain():
    app, engine, pp, a, b, fid = paid_family()
    with engine.begin() as c:
        c.execute(sa.update(db.event).where(db.event.c.family_id == fid, db.event.c.seq == 3).values(body_json='{"edited": true}'))
    assert "Record changed at entry 3" in a.get(f"/f/{fid}/record").text


def test_verify_button_rechecks_with_paypal():
    app, engine, pp, a, b, fid = paid_family()
    page = a.get(f"/f/{fid}/record").text
    n = sum(1 for k, _ in pp.calls if k == "get_capture")
    a.post(f"/f/{fid}/record/verify", data={"csrf": csrf(page)})
    assert sum(1 for k, _ in pp.calls if k == "get_capture") == n + 1


def test_export_has_disclaimer_and_no_agreement_text():
    app, engine, pp, a, b, fid = paid_family()
    page = a.get(f"/f/{fid}/record/export").text
    assert "Not legal advice. Sandbox demonstration." in page
    assert "shall be paid 60% by the Father" not in page and "Unreimbursed medical" not in page


def load_verify():
    spec = importlib.util.spec_from_file_location("verify_script", ROOT / "scripts" / "verify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_verify_script_exit_codes(capsys):
    app, engine, pp, a, b, fid = paid_family()
    verify = load_verify()
    assert verify.run(engine, pp, fid) == 0
    out = capsys.readouterr().out
    assert "completed verified" in out and "CHAIN OK" in out
    with engine.begin() as c:  # PayPal now reports a different amount than Between recorded
        c.execute(sa.update(db.payment).values(amount_minor=25000))
    assert verify.run(engine, pp, fid) == 1
    assert "mismatch:amount" in capsys.readouterr().out
