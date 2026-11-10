import os
import re
from pathlib import Path

import sqlalchemy as sa

from between import db
from keys import PLAN1
from webutil import csrf, fake_ai, family_with_rules, make, submit_expense

DOC1 = (Path(__file__).parent.parent / "samples" / "agreements" / PLAN1["doc"]).read_text()
PNG = (Path(__file__).parent.parent / "samples" / "receipts" / "ortho_420.png").read_bytes()


def expense_id(resp):
    return re.search(r"/expenses/([0-9a-f]+)$", resp.headers["location"]).group(1)


def test_receipt_bytes_not_persisted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app, engine = make(ai=fake_ai(PLAN1))
    a, b, fid = family_with_rules(app, DOC1)
    assert submit_expense(a, fid, "medical", receipt=PNG).status_code == 303
    assert list(tmp_path.iterdir()) == []
    assert not any(isinstance(col.type, sa.LargeBinary) for t in db.metadata.tables.values() for col in t.columns)
    with engine.connect() as c:
        dump = repr([c.execute(sa.select(t)).all() for t in db.metadata.sorted_tables])
    assert "PNG" not in dump and "IHDR" not in dump


def test_model_total_needs_payer_confirmation():
    app, _ = make(ai=fake_ai(PLAN1, receipt_total=42000))
    a, b, fid = family_with_rules(app, DOC1)
    page = a.get(f"/f/{fid}/expenses/new").text
    r = a.post(f"/f/{fid}/expenses/new", data={"csrf": csrf(page), "category": "medical"},
               files={"receipt": ("r.png", PNG, "image/png")})
    assert 'name="amount" value="420.00"' in r.text and "Is that what you paid?" in r.text
    done = submit_expense(a, fid, "medical", receipt=PNG + b"2", amount="419.00")
    card = a.get(done.headers["location"]).text
    assert "$251.40" in card and "$419.00" in card  # 60% of the confirmed $419.00, not of the AI's $420.00


def test_bad_amount_is_refused_with_field_error():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = family_with_rules(app, DOC1)
    r = submit_expense(a, fid, "medical", amount="12.345")
    assert r.status_code == 400 and "two decimal places" in r.text


def test_duplicate_receipt_rejected():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = family_with_rules(app, DOC1)
    assert submit_expense(a, fid, "medical", receipt=PNG).status_code == 303
    r = submit_expense(b, fid, "medical", receipt=PNG)
    assert r.status_code == 409 and "already" in r.text


def test_decision_cites_sections():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = family_with_rules(app, DOC1)
    card = a.get(submit_expense(a, fid, "medical", receipt=PNG).headers["location"]).text
    assert "$252.00" in card and "Father owes Mother" in card
    assert "6.1" in card and "7.2" in card and "shall be paid 60% by the Father" in card


def test_consent_flow_unblocks_activity_expense():
    app, _ = make(ai=fake_ai(PLAN1, receipt_total=25000))
    a, b, fid = family_with_rules(app, DOC1)
    loc = submit_expense(a, fid, "extracurricular", receipt=PNG).headers["location"]
    assert "Needs agreement first" in a.get(loc).text
    page = a.get(f"/f/{fid}/expenses/new").text
    a.post(f"/f/{fid}/consents", data={"csrf": csrf(page), "category": "extracurricular", "max": "300", "note": "soccer camp"})
    home_b = b.get(f"/f/{fid}").text
    cid = re.search(r'/consents/([0-9a-f]+)/agree', home_b).group(1)
    assert b.post(f"/f/{fid}/consents/{cid}/agree", data={"csrf": csrf(home_b)}, follow_redirects=False).status_code == 303
    card = a.get(loc).text
    a.post(loc + "/redecide", data={"csrf": csrf(card)})
    card = a.get(loc).text
    assert "Payable" in card and "$125.00" in card


def test_only_other_parent_can_agree_consent():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = family_with_rules(app, DOC1)
    page = a.get(f"/f/{fid}/expenses/new").text
    a.post(f"/f/{fid}/consents", data={"csrf": csrf(page), "category": "extracurricular", "max": "300", "note": "x"})
    home_a = a.get(f"/f/{fid}").text
    assert "/agree" not in home_a
    import sqlalchemy as sa2
    with app.state.engine.connect() as c:
        cid = c.execute(sa2.select(db.consent.c.id)).scalar()
    r = a.post(f"/f/{fid}/consents/{cid}/agree", data={"csrf": csrf(a.get(f"/f/{fid}/expenses/new").text)}, follow_redirects=False)
    assert r.status_code == 403


def test_consent_note_not_in_record():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = family_with_rules(app, DOC1)
    page = a.get(f"/f/{fid}/expenses/new").text
    a.post(f"/f/{fid}/consents", data={"csrf": csrf(page), "category": "extracurricular", "max": "300", "note": "PRIVATE-NOTE-42"})
    with app.state.engine.connect() as c:
        bodies = " ".join(r.body_json for r in c.execute(sa.select(db.event.c.body_json)))
    assert "PRIVATE-NOTE-42" not in bodies
