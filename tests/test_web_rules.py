import re
from pathlib import Path

import sqlalchemy as sa

from between import db
from between.extraction import AIUnavailable
from keys import PLAN1, PLAN3
from webutil import csrf, fake_ai, make, two_parents, upload

DOCS = Path(__file__).parent.parent / "samples" / "agreements"
PLAN3_WITH_CONFLICT = {**PLAN3, "rules": PLAN3["rules"] + [
    {"id": "x1", "kind": "split", "category": "medical", "params": {"shares": {"A": 30, "B": 70}},
     "source": {"quote": "Dad pays 70%, Mom pays 30%.", "page": 1, "section": "Item 3"}},
    {"id": "x2", "kind": "split", "category": "medical", "params": {"shares": {"A": 50, "B": 50}},
     "source": {"quote": "All medical costs will be split equally between Mom and Dad.", "page": 3, "section": "A.1"}}]}


def approve(client, fid):
    page = client.get(f"/f/{fid}/rules").text
    rsid = re.search(r'action="/f/[^/]+/rules/([^/]+)/approve"', page).group(1)
    h = re.search(r'name="hash_seen" value="([0-9a-f]{64})"', page).group(1)
    return client.post(f"/f/{fid}/rules/{rsid}/approve", data={"csrf": csrf(page), "hash_seen": h}, follow_redirects=False)


def test_upload_extract_review_and_both_approve():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = two_parents(app)
    assert upload(a, fid, (DOCS / PLAN1["doc"]).read_text()).status_code == 303
    page = a.get(f"/f/{fid}/rules").text
    assert page.count('class="rule agreement"') == 11 and "shall be paid 60% by the Father" in page
    assert "Page 2" in page and "6.1" in page
    assert approve(a, fid).status_code == 303 and approve(b, fid).status_code == 303
    assert "Approved by both of you" in a.get(f"/f/{fid}").text


def test_ai_unavailable_stores_nothing():
    app, engine = make(ai=None)
    a, b, fid = two_parents(app)
    r = upload(a, fid, (DOCS / PLAN1["doc"]).read_text())
    assert r.status_code == 503 and "nothing was changed" in r.text
    with engine.connect() as c:
        assert c.execute(sa.select(sa.func.count()).select_from(db.agreement)).scalar() == 0
        assert c.execute(sa.select(sa.func.count()).select_from(db.ruleset)).scalar() == 0


def test_other_parent_answer_not_in_html_until_both():
    app, _ = make(ai=fake_ai(PLAN3_WITH_CONFLICT))
    a, b, fid = two_parents(app, label="Mom", other="Dad")
    upload(a, fid, (DOCS / PLAN3["doc"]).read_text())
    page = b.get(f"/f/{fid}/rules").text
    qid = re.search(r'name="question_id" value="(q\d+)"', page).group(1)
    rsid = re.search(r'name="ruleset_id" value="([^"]+)"', page).group(1)
    b.post(f"/f/{fid}/questions/{qid}/answer", data={"csrf": csrf(page), "ruleset_id": rsid, "choice": "use_1"})
    a_page = a.get(f"/f/{fid}/rules").text
    assert "Dad chose" not in a_page and "data-other-choice" not in a_page
    assert "You'll both see the answers once you've both answered" in a_page


def test_resolution_banner_copy_present():
    app, _ = make(ai=fake_ai(PLAN3_WITH_CONFLICT))
    a, b, fid = two_parents(app, label="Mom", other="Dad")
    upload(a, fid, (DOCS / PLAN3["doc"]).read_text())
    for client in (a, b):
        page = client.get(f"/f/{fid}/rules").text
        qid = re.search(r'name="question_id" value="(q\d+)"', page).group(1)
        rsid = re.search(r'name="ruleset_id" value="([^"]+)"', page).group(1)
        client.post(f"/f/{fid}/questions/{qid}/answer", data={"csrf": csrf(page), "ruleset_id": rsid, "choice": "use_0"})
    page = a.get(f"/f/{fid}/rules").text
    assert "Your working arrangement in Between. It does not change your legal agreement." in page
    assert 'class="rule resolution"' in page and "Resolution R1" in page
