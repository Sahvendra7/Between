"""Start a family, invite the other parent, and the family's home page."""
from __future__ import annotations

import hashlib
import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from between import access, db, demo, record, ruleset as RS
from between.web.deps import actor, checked_form, get_conn, now, render, require_family

router = APIRouter()
JOIN_ERRORS = {"used": "This invite link has already been used.", "expired": "This invite link has expired. Ask for a new one.",
               "revoked": "This invite link was replaced by a newer one.", "unknown": "This invite link isn't recognised."}


def parents(conn, fid) -> dict[str, dict]:
    return {r["role"]: dict(r) for r in conn.execute(sa.select(db.parent).where(db.parent.c.family_id == fid)).mappings()}


def labels(conn, fid) -> dict[str, str]:
    return {role: p["label"] for role, p in parents(conn, fid).items()}


def other_joined(conn, fid, role) -> bool:
    return conn.execute(sa.select(db.invite.c.token_hash).where(
        db.invite.c.family_id == fid, db.invite.c.role == role, db.invite.c.used_at.is_not(None))).first() is not None


def home_context(conn, request, s, invite_url=None):
    from between.web.summary import family_summary
    rs, approvals = RS.current(conn, s.family_id)
    other = "B" if s.role == "A" else "A"
    return dict(s=s, fid=s.family_id, parents=parents(conn, s.family_id), rs=rs, approvals=approvals,
                open_questions=[q for q in (rs or {}).get("questions", [])
                                if q["id"] not in {r["source"].get("question_id") for r in rs["rules"] if r.get("origin") == "resolution"}] if rs else [],
                invite_url=invite_url, other_joined=other_joined(conn, s.family_id, other),
                demo_family=request.app.state.settings.demo_mode and demo.is_visitor_family(conn, s.family_id),
                **family_summary(conn, s))


@router.get("/")
def start(request: Request):
    return render(request, "start.html")


@router.post("/families")
def create_family(request: Request, role_label: str = Form(...), other_label: str = Form(...),
                  display_name: str = Form(...), paypal_email: str = Form(...), conn=Depends(get_conn)):
    settings = request.app.state.settings
    role_label, other_label, display_name = role_label.strip()[:40], other_label.strip()[:40], display_name.strip()[:60]
    if not role_label or not other_label or role_label.lower() == other_label.lower() or not display_name:
        return render(request, "start.html", 400, error="Give both parents different names as written in your agreement.")
    try:
        demo.check_paypal_email(paypal_email, settings)
    except demo.DemoGuard as g:
        return render(request, "start.html", 400, error=g.message)
    t, fid = now(), uuid.uuid4().hex[:12]
    conn.execute(sa.insert(db.family).values(id=fid, created_at=t, currency="USD"))
    conn.execute(sa.insert(db.parent).values(family_id=fid, role="A", label=role_label, display_name=display_name,
                                             paypal_email=paypal_email.strip().lower()))
    conn.execute(sa.insert(db.parent).values(family_id=fid, role="B", label=other_label, display_name="(invited)"))
    raw = access.create_session(conn, fid, "A", t)
    s = access.session_for(conn, raw, t)
    record.append(conn, fid, "family.created", {"family_id": fid, "labels": {"A": role_label, "B": other_label}}, actor(s), now=t)
    token = access.create_invite(conn, fid, "B", t)
    resp = render(request, "home.html", **home_context(conn, request, s, invite_url=f"{settings.base_url}/join/{token}"))
    resp.set_cookie(access.COOKIE_NAME, raw, **access.cookie_kwargs(settings))
    return resp


def _invite_row(conn, token):
    h = hashlib.sha256((token or "").encode()).hexdigest()
    return conn.execute(sa.select(db.invite).where(db.invite.c.token_hash == h)).mappings().first()


@router.get("/join/{token}")
def join_form(request: Request, token: str, conn=Depends(get_conn)):
    row = _invite_row(conn, token)
    if row is None or row["used_at"] or row["revoked_at"]:
        code = "unknown" if row is None else ("used" if row["used_at"] else "revoked")
        return render(request, "join_error.html", 400, message=JOIN_ERRORS[code])
    return render(request, "join.html", token=token, labels=labels(conn, row["family_id"]), role=row["role"])


@router.post("/join/{token}")
def join(request: Request, token: str, display_name: str = Form(...), paypal_email: str = Form(...), conn=Depends(get_conn)):
    settings = request.app.state.settings
    row = _invite_row(conn, token)
    try:
        demo.check_paypal_email(paypal_email, settings)
    except demo.DemoGuard as g:
        return render(request, "join.html", 400, token=token, error=g.message,
                      labels=labels(conn, row["family_id"]) if row else {}, role=row["role"] if row else "B")
    t = now()
    try:
        raw = access.redeem_invite(conn, token, t)
    except access.AccessError as e:
        return render(request, "join_error.html", 400, message=JOIN_ERRORS[e.code])
    s = access.session_for(conn, raw, t)
    conn.execute(sa.update(db.parent).where(db.parent.c.family_id == s.family_id, db.parent.c.role == s.role)
                 .values(display_name=display_name.strip()[:60] or "Parent", paypal_email=paypal_email.strip().lower()))
    record.append(conn, s.family_id, "parent.joined", {"role": s.role}, actor(s), now=t)
    resp = RedirectResponse(f"/f/{s.family_id}", status_code=303)
    resp.set_cookie(access.COOKIE_NAME, raw, **access.cookie_kwargs(settings))
    return resp


@router.get("/f/{fid}")
def home(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    return render(request, "home.html", **home_context(conn, request, s))


@router.post("/f/{fid}/invite/rotate")
async def rotate_invite(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    await checked_form(request, s)
    other = "B" if s.role == "A" else "A"
    if other_joined(conn, fid, other):
        return render(request, "home.html", 409, error="The other parent has already joined, so their link can't be replaced.",
                      **home_context(conn, request, s))
    token = access.create_invite(conn, fid, other, now())
    return render(request, "home.html", **home_context(conn, request, s, invite_url=f"{request.app.state.settings.base_url}/join/{token}"))
