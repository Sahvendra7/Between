"""Request plumbing: one DB transaction per request, the parent's session, CSRF, role checks."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, Request

from between import access


def now() -> datetime:
    return datetime.now(timezone.utc)


def get_conn(request: Request):
    with request.app.state.engine.begin() as conn:
        yield conn


def current_session(request: Request, conn) -> access.Session | None:
    return access.session_for(conn, request.cookies.get(access.COOKIE_NAME), now())


def require_family(request: Request, conn, family_id: str) -> access.Session:
    s = current_session(request, conn)
    if s is None or s.family_id != family_id:
        raise HTTPException(status_code=403, detail="Not your family")
    return s


async def checked_form(request: Request, s: access.Session):
    form = await request.form()
    if not access.check_csrf(s, form.get("csrf")):
        raise HTTPException(status_code=403, detail="Form expired. Reload the page and try again.")
    return form


def actor(s: access.Session) -> dict:
    return {"kind": "parent", "role": s.role, "session_ref": s.ref}


def render(request: Request, name: str, status: int = 200, **ctx):
    return request.app.state.templates.TemplateResponse(request, name, ctx, status_code=status)
