"""The family's record: every event with its actor and chain hash, payments as PayPal reports them,
a button that re-checks every payment with PayPal, and a printable export."""
from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from between import db, record
from between.reconcile import complete_if_approved
from between.web.deps import actor, checked_form, get_conn, now, render, require_family
from between.web.routes_family import labels

router = APIRouter()


def record_context(conn, fid):
    names = labels(conn, fid)

    def who(a):
        return {"parent": names.get(a.get("role"), a.get("role")), "paypal": "PayPal", "system": "Between"}.get(a.get("kind"), "?")

    events = [{**e, "who": who(e["actor"])} for e in record.events(conn, fid)]
    pays = [dict(p) for p in conn.execute(
        sa.select(db.payment, db.expense.c.category).join(db.expense, db.expense.c.id == db.payment.c.expense_id)
        .where(db.expense.c.family_id == fid).order_by(db.payment.c.id)).mappings()]
    return dict(events=events, payments=pays, broken_at=record.check(conn, fid), names=names)


@router.get("/f/{fid}/record")
def record_page(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    return render(request, "record.html", s=s, fid=fid, **record_context(conn, fid))


@router.post("/f/{fid}/record/verify")
async def record_verify(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    await checked_form(request, s)
    pp = request.app.state.pp
    if pp is not None:
        for p in record_context(conn, fid)["payments"]:
            if p["order_id"] and p["status"] != "cancelled":
                complete_if_approved(conn, pp, p["id"], actor(s), now())
    return RedirectResponse(f"/f/{fid}/record", status_code=303)


@router.get("/f/{fid}/record/export")
def record_export(request: Request, fid: str, conn=Depends(get_conn)):
    require_family(request, conn, fid)
    return render(request, "record_export.html", fid=fid, generated=now(), **record_context(conn, fid))
