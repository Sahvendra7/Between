import pytest

from between import demo
from between.config import Settings
from keys import PLAN1
from webutil import fake_ai, make, two_parents, upload

DEMO, LIVE = Settings(demo_mode=True), Settings(demo_mode=False)


def test_guards_in_demo_mode():
    with pytest.raises(demo.DemoGuard) as e:
        demo.check_agreement_text("A real agreement", DEMO)
    assert e.value.code == "not_synthetic"
    with pytest.raises(demo.DemoGuard) as e:
        demo.check_agreement_text(demo.SYNTHETIC_MARKER + "x" * 60001, DEMO)
    assert e.value.code == "too_long"
    demo.check_agreement_text("A real agreement", LIVE)  # outside demo mode only length/emptiness applies
    with pytest.raises(demo.DemoGuard):
        demo.check_paypal_email("jane@gmail.com", DEMO)
    demo.check_paypal_email("sb-1@business.example.com", DEMO)
    with pytest.raises(demo.DemoGuard) as e:
        demo.check_upload("image/gif", 10, DEMO)
    assert e.value.code == "bad_type"
    with pytest.raises(demo.DemoGuard) as e:
        demo.check_upload("image/png", 2 * 1024 * 1024 + 1, DEMO)
    assert e.value.code == "too_big"


def test_non_synthetic_agreement_refused_in_demo_mode():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = two_parents(app)
    r = upload(a, fid, "=== Page 1 ===\nA real agreement between two real people.")
    assert r.status_code == 400 and "synthetic" in r.text


def test_oversized_agreement_refused_in_demo_mode():
    app, _ = make(ai=fake_ai(PLAN1))
    a, b, fid = two_parents(app)
    r = upload(a, fid, demo.SYNTHETIC_MARKER + "\n" + "x" * 60001)
    assert r.status_code == 400 and "too long" in r.text


from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi.testclient import TestClient

from between import db, engine as E, ruleset as RS

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=timezone.utc)
SEEDED = Settings(demo_mode=True, demo_parent_a_email="sb-a@personal.example.com", demo_parent_b_email="sb-b@personal.example.com")


def counts(conn):
    return {t.name: conn.execute(sa.select(sa.func.count()).select_from(t)).scalar() for t in db.metadata.sorted_tables}


def test_seed_is_idempotent(conn):
    first = demo.seed(conn, SEEDED, NOW)
    before = counts(conn)
    assert demo.seed(conn, SEEDED, NOW) == first and counts(conn) == before
    rs, approvals = RS.current(conn, first)
    assert len(rs["rules"]) == 11 and E.is_approved(rs, approvals)


def test_seed_never_overwrites(conn):
    fid = demo.seed(conn, SEEDED, NOW)
    conn.execute(sa.update(db.parent).where(db.parent.c.family_id == fid, db.parent.c.role == "A").values(display_name="Changed"))
    demo.seed(conn, SEEDED, NOW)
    assert conn.execute(sa.select(db.parent.c.display_name).where(db.parent.c.family_id == fid, db.parent.c.role == "A")).scalar() == "Changed"


def test_new_demo_family_isolated(conn):
    f1, a1, b1 = demo.new_demo_family(conn, SEEDED, NOW)
    f2, a2, b2 = demo.new_demo_family(conn, SEEDED, NOW)
    assert f1 != f2 and len({a1, b1, a2, b2}) == 4
    rs1, _ = RS.current(conn, f1)
    rs2, _ = RS.current(conn, f2)
    assert rs1["id"] != rs2["id"] and len(rs1["rules"]) == 11


def test_try_demo_then_switch_parent():
    app, _ = make(demo_parent_a_email="sb-a@personal.example.com", demo_parent_b_email="sb-b@personal.example.com")
    c = TestClient(app)
    r = c.post("/demo/new", follow_redirects=False)
    fid = r.headers["location"].rsplit("/", 1)[1]
    home = c.get(f"/f/{fid}").text
    assert "You're viewing as Mother" in home
    import re
    tok = re.search(r'name="csrf" value="([^"]+)"', home).group(1)
    c.post(f"/demo/switch/{fid}", data={"csrf": tok})
    assert "You're viewing as Father" in c.get(f"/f/{fid}").text


def test_switch_refused_for_real_families_and_outside_demo_mode():
    app, _ = make()
    a, b, fid = two_parents(app)
    page = a.get(f"/f/{fid}/agreement").text
    import re
    tok = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
    assert a.post(f"/demo/switch/{fid}", data={"csrf": tok}).status_code == 403
    app2, _ = make(demo_mode=False, demo_parent_a_email="sb-a@personal.example.com", demo_parent_b_email="sb-b@personal.example.com")
    assert TestClient(app2).post("/demo/new").status_code == 404
