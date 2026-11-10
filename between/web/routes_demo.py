"""Demo-only shortcuts (BETWEEN_DEMO_MODE=1): a fresh synthetic family per visitor, and switching
between the two parents of *that* family so one person can try both sides. Real families are untouched."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from between import access, demo, record
from between.web.deps import checked_form, get_conn, now, require_family

router = APIRouter()


@router.post("/demo/new")
def demo_new(request: Request, conn=Depends(get_conn)):
    settings = request.app.state.settings
    if not settings.demo_mode:
        raise HTTPException(status_code=404)
    t = now()
    fid, invite_a, _ = demo.new_demo_family(conn, settings, t)
    raw = access.redeem_invite(conn, invite_a, t)
    resp = RedirectResponse(f"/f/{fid}", status_code=303)
    resp.set_cookie(access.COOKIE_NAME, raw, **access.cookie_kwargs(settings))
    return resp


@router.post("/demo/switch/{fid}")
async def demo_switch(request: Request, fid: str, conn=Depends(get_conn)):
    settings = request.app.state.settings
    s = require_family(request, conn, fid)
    await checked_form(request, s)
    if not settings.demo_mode or not demo.is_visitor_family(conn, fid):
        raise HTTPException(status_code=403, detail="Only demo families can switch parents.")
    t, other = now(), "B" if s.role == "A" else "A"
    raw = access.create_session(conn, fid, other, t)
    record.append(conn, fid, "demo.switched", {"to": other}, {"kind": "parent", "role": s.role, "session_ref": s.ref}, now=t)
    resp = RedirectResponse(f"/f/{fid}", status_code=303)
    resp.set_cookie(access.COOKIE_NAME, raw, **access.cookie_kwargs(settings))
    return resp
