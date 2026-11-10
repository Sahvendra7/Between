"""Read-only parenting-time calendar (Bryntum Calendar Community, MIT) with expenses on their dates."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from between import db, record, schedule as SC
from between.money import fmt_usd
from between.web.deps import actor, checked_form, get_conn, now, render, require_family
from between.web.present import category_name
from between.web.routes_family import labels
from between.web.summary import family_summary

router = APIRouter()


def _schedule(conn, fid):
    row = conn.execute(sa.select(db.schedule).where(db.schedule.c.family_id == fid)).mappings().first()
    if row is None:
        return None
    return {**json.loads(row["json"]), "anchor_date": row["anchor_date"], "first_parent": row["first_parent"], "set_by": row["set_by"]}


def _local_now() -> datetime:
    return now().astimezone(timezone.utc).replace(tzinfo=None)


@router.get("/f/{fid}/calendar")
def calendar_page(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    return render(request, "calendar.html", s=s, fid=fid, sched=_schedule(conn, fid), names=labels(conn, fid))


@router.get("/f/{fid}/calendar.json")
def calendar_json(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    names, sched, t = labels(conn, fid), _schedule(conn, fid), _local_now()
    events = []
    if sched:
        for i, b in enumerate(SC.expand(sched, (t - timedelta(days=42)).date(), 120)):
            events.append({"id": f"c{i}", "kind": "custody", "name": f"With {names[b['resourceId']]}", **b})
    for e in family_summary(conn, s)["expenses"]:
        events.append({"id": f"e{e['id']}", "kind": "expense", "allDay": True, "startDate": e["incurred_on"],
                       "endDate": e["incurred_on"], "resourceId": e["paid_by"],
                       "name": f"{category_name(e['category'])} {fmt_usd(e['amount_minor'])} · {e['label']}"})
    return {"now": t.isoformat(timespec="seconds"), "today": t.date().isoformat(),
            "resources": [{"id": "A", "name": names["A"], "eventColor": "teal"}, {"id": "B", "name": names["B"], "eventColor": "orange"}],
            "events": events, "source": (sched or {}).get("source")}


@router.post("/f/{fid}/calendar/anchor")
async def set_anchor(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    form = await checked_form(request, s)
    sched = _schedule(conn, fid)
    if sched is None or form.get("parent") not in ("A", "B"):
        raise HTTPException(status_code=400, detail="There's no parenting-time pattern to set yet.")
    anchor = SC.last_changeover(sched, _local_now()).isoformat()
    conn.execute(sa.update(db.schedule).where(db.schedule.c.family_id == fid)
                 .values(anchor_date=anchor, first_parent=form["parent"], set_by=s.role, at=now()))
    record.append(conn, fid, "schedule.anchor_set", {"anchor_date": anchor, "first_parent": form["parent"]}, actor(s), now=now())
    return RedirectResponse(f"/f/{fid}/calendar", status_code=303)


def store_schedule(conn, fid: str, agreement_id: str, sched: dict | None, anchor=None, first_parent=None, set_by=None) -> None:
    if not sched:
        return
    conn.execute(sa.delete(db.schedule).where(db.schedule.c.family_id == fid))
    conn.execute(sa.insert(db.schedule).values(family_id=fid, agreement_id=agreement_id, json=json.dumps(sched),
                                               anchor_date=anchor, first_parent=first_parent, set_by=set_by, at=now()))
