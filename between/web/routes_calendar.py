"""Parenting-time calendar (Bryntum Calendar Community, MIT) with expenses on their dates, and swap requests:
a parent drags across days in the other parent's time (or uses the form) to ask for them; only the other
parent can agree. Agreed swaps are a working arrangement and don't change the parenting plan."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timedelta, timezone

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


MAX_SWAP_DAYS = 14
LIVE_SWAP = ("pending", "accepted")


def _swaps(conn, fid, statuses=LIVE_SWAP) -> list[dict]:
    q = sa.select(db.swap).where(db.swap.c.family_id == fid, db.swap.c.status.in_(statuses)).order_by(db.swap.c.start_date)
    return [dict(r) for r in conn.execute(q).mappings()]


def _owner_on(sched, d: date) -> str | None:
    """Who has the child at noon on d under the agreement's pattern."""
    noon = datetime.combine(d, time(12)).isoformat()
    return next((b["resourceId"] for b in SC.expand(sched, d - timedelta(days=8), 16) if b["startDate"] <= noon < b["endDate"]), None)


@router.get("/f/{fid}/calendar")
def calendar_page(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    today = _local_now().date().isoformat()
    swaps = [w for w in _swaps(conn, fid) if w["end_date"] > today]
    return render(request, "calendar.html", s=s, fid=fid, sched=_schedule(conn, fid), names=labels(conn, fid),
                  swaps=swaps, today=today)


@router.post("/f/{fid}/calendar/swaps")
async def request_swap(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    form = await checked_form(request, s)
    try:
        start, end = date.fromisoformat(form.get("start", "")), date.fromisoformat(form.get("end", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Choose the first day and the day after the last day.") from None
    if end <= start or start < _local_now().date() or (end - start).days > MAX_SWAP_DAYS:
        raise HTTPException(status_code=400, detail=f"Choose up to {MAX_SWAP_DAYS} days, starting today or later.")
    sched = _schedule(conn, fid)
    if not sched or not sched.get("anchor_date"):
        raise HTTPException(status_code=400, detail="Set whose week it is first, so Between knows whose days these are.")
    other = "B" if s.role == "A" else "A"
    if not any(_owner_on(sched, start + timedelta(days=i)) == other for i in range((end - start).days)):
        raise HTTPException(status_code=400, detail="Those days are already with you.")
    if any(w["start_date"] < end.isoformat() and start.isoformat() < w["end_date"] for w in _swaps(conn, fid)):
        raise HTTPException(status_code=409, detail="Those days overlap a swap that's already asked for or agreed.")
    sid, t = uuid.uuid4().hex[:12], now()
    conn.execute(sa.insert(db.swap).values(id=sid, family_id=fid, requested_by=s.role, start_date=start.isoformat(),
                                           end_date=end.isoformat(), status="pending", at=t))
    record.append(conn, fid, "swap.requested", {"swap_id": sid, "start": start.isoformat(), "end": end.isoformat(),
                                                "by": s.role}, actor(s), now=t)
    return RedirectResponse(f"/f/{fid}/calendar", status_code=303)


@router.post("/f/{fid}/calendar/swaps/{sid}/{verb}")
async def decide_swap(request: Request, fid: str, sid: str, verb: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    await checked_form(request, s)
    w = conn.execute(sa.select(db.swap).where(db.swap.c.id == sid, db.swap.c.family_id == fid)).mappings().first()
    if w is None or verb not in ("accept", "decline", "cancel"):
        raise HTTPException(status_code=404)
    if (verb == "cancel") != (s.role == w["requested_by"]):
        raise HTTPException(status_code=403, detail="Only the other parent can agree or decline; only the asker can cancel.")
    if w["status"] != "pending":
        raise HTTPException(status_code=409, detail="This swap was already decided.")
    status = {"accept": "accepted", "decline": "declined", "cancel": "cancelled"}[verb]
    t = now()
    conn.execute(sa.update(db.swap).where(db.swap.c.id == sid).values(status=status, decided_by=s.role, at=t))
    record.append(conn, fid, f"swap.{status}", {"swap_id": sid, "start": w["start_date"], "end": w["end_date"]}, actor(s), now=t)
    return RedirectResponse(f"/f/{fid}/calendar", status_code=303)


@router.get("/f/{fid}/calendar.json")
def calendar_json(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    names, sched, t = labels(conn, fid), _schedule(conn, fid), _local_now()
    events = []
    if sched:
        for i, b in enumerate(SC.expand(sched, (t - timedelta(days=42)).date(), 120)):
            events.append({"id": f"c{i}", "kind": "custody", "name": f"With {names[b['resourceId']]}", **b})
    for w in _swaps(conn, fid):
        other = "B" if w["requested_by"] == "A" else "A"
        name = (f"With {names[w['requested_by']]} · swap agreed" if w["status"] == "accepted"
                else f"{names[w['requested_by']]} asks for these days · waiting for {names[other]}")
        events.append({"id": f"s{w['id']}", "kind": "swap-agreed" if w["status"] == "accepted" else "swap-pending",
                       "allDay": True, "startDate": w["start_date"], "endDate": w["end_date"],
                       "resourceId": w["requested_by"], "name": name})
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
