"""Swap requests: one parent asks for days in the other's time (drag on the calendar or the form);
only the other parent can agree; agreed swaps show on the calendar and go into the record."""
import re
from datetime import date, timedelta

import sqlalchemy as sa

from between import db, record
from test_web_calendar import demo_family
from webutil import csrf


def switch(c, fid):
    page = c.get(f"/f/{fid}").text
    c.post(f"/demo/switch/{fid}", data={"csrf": csrf(page)})


def father_days(c, fid, n=2):
    """The first n whole days inside Father's next week (the demo seeds Mother for this week)."""
    data = c.get(f"/f/{fid}/calendar.json").json()
    b = next(e for e in data["events"] if e["kind"] == "custody" and e["resourceId"] == "B" and e["startDate"] > data["now"])
    start = date.fromisoformat(b["startDate"][:10]) + timedelta(days=1)
    return start.isoformat(), (start + timedelta(days=n)).isoformat()


def ask(c, fid, start, end):
    page = c.get(f"/f/{fid}/calendar").text
    return c.post(f"/f/{fid}/calendar/swaps", data={"csrf": csrf(page), "start": start, "end": end}, follow_redirects=False)


def decide(c, fid, verb):
    page = c.get(f"/f/{fid}/calendar").text
    sid = re.search(rf'action="/f/{fid}/calendar/swaps/([0-9a-f]+)/{verb}"', page).group(1)
    return c.post(f"/f/{fid}/calendar/swaps/{sid}/{verb}", data={"csrf": csrf(page)}, follow_redirects=False)


def test_request_then_other_parent_agrees():
    app, c, fid = demo_family()
    start, end = father_days(c, fid)
    assert ask(c, fid, start, end).status_code == 303
    page = c.get(f"/f/{fid}/calendar").text
    assert "Waiting for Father" in page and f'/calendar/swaps/' in page and "/accept" not in page  # the asker can't accept
    switch(c, fid)
    assert decide(c, fid, "accept").status_code == 303
    events = c.get(f"/f/{fid}/calendar.json").json()["events"]
    swap = next(e for e in events if e["kind"] == "swap-agreed")
    assert (swap["startDate"], swap["endDate"], swap["resourceId"]) == (start, end, "A")
    with app.state.engine.connect() as conn:
        types = [e["type"] for e in record.events(conn, fid)]
    assert "swap.requested" in types and "swap.accepted" in types


def test_pending_swap_shows_and_can_be_declined():
    app, c, fid = demo_family()
    start, end = father_days(c, fid)
    ask(c, fid, start, end)
    assert any(e["kind"] == "swap-pending" for e in c.get(f"/f/{fid}/calendar.json").json()["events"])
    switch(c, fid)
    decide(c, fid, "decline")
    assert not any(e["kind"].startswith("swap") for e in c.get(f"/f/{fid}/calendar.json").json()["events"])


def test_refuses_own_days_past_days_long_and_overlapping_requests():
    app, c, fid = demo_family()
    start, end = father_days(c, fid)
    mine = (date.fromisoformat(start) - timedelta(days=7)).isoformat()
    past = (date.today() - timedelta(days=3)).isoformat()
    assert ask(c, fid, mine, (date.fromisoformat(mine) + timedelta(days=1)).isoformat()).status_code == 400
    assert ask(c, fid, past, (date.today() - timedelta(days=1)).isoformat()).status_code == 400
    assert ask(c, fid, start, (date.fromisoformat(start) + timedelta(days=20)).isoformat()).status_code == 400
    assert ask(c, fid, end, start).status_code == 400 and ask(c, fid, "x", "y").status_code == 400
    assert ask(c, fid, start, end).status_code == 303
    assert ask(c, fid, start, end).status_code == 409
