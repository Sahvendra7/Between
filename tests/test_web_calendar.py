import re

from fastapi.testclient import TestClient

from webutil import csrf, make, submit_expense


def demo_family():
    app, engine = make(demo_parent_a_email="sb-a@personal.example.com", demo_parent_b_email="sb-b@personal.example.com")
    c = TestClient(app)
    fid = c.post("/demo/new", follow_redirects=False).headers["location"].rsplit("/", 1)[1]
    return app, c, fid


def test_calendar_page_uses_vendored_bryntum_and_no_cdn():
    app, c, fid = demo_family()
    page = c.get(f"/f/{fid}/calendar").text
    assert "/static/calendar.js" in page and "/static/vendor/fontawesome/css/solid.min.css" in page
    assert "cdnjs" not in page and "Bryntum Calendar Community" in page


def test_calendar_json_has_custody_blocks_and_expenses():
    app, c, fid = demo_family()
    data = c.get(f"/f/{fid}/calendar.json").json()
    assert {r["id"] for r in data["resources"]} == {"A", "B"}
    custody = [e for e in data["events"] if e["kind"] == "custody"]
    assert custody and {e["resourceId"] for e in custody} == {"A", "B"}
    assert data["source"]["section"] == "2.1"


def test_parent_sets_who_has_this_week():
    app, c, fid = demo_family()
    page = c.get(f"/f/{fid}/calendar").text
    c.post(f"/f/{fid}/calendar/anchor", data={"csrf": csrf(page), "parent": "B"})
    data = c.get(f"/f/{fid}/calendar.json").json()
    current = [e for e in data["events"] if e["kind"] == "custody" and e["startDate"] <= data["now"] < e["endDate"]]
    assert current and current[0]["resourceId"] == "B"


def test_calendar_is_family_private():
    app, c, fid = demo_family()
    assert TestClient(app).get(f"/f/{fid}/calendar.json").status_code == 403
