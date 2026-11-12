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


def public_base(request: Request) -> str:
    """Where invite links and PayPal return URLs point: the frontend origin that proxied this request, if allowlisted."""
    settings = request.app.state.settings
    origin = request.headers.get("x-between-origin", "").rstrip("/")
    return origin if origin and origin in settings.frontend_origins else settings.base_url


def wants_json(request: Request) -> bool:
    return request.headers.get("x-between-json") == "1"


def _annotate(value, labels):
    """Adds each rule's plain-English wording (present.describe_rule), so the frontend never re-implements it."""
    from between.web.present import describe_rule
    if isinstance(value, list):
        return [_annotate(v, labels) for v in value]
    if isinstance(value, dict):
        out = {k: _annotate(v, labels) for k, v in value.items()}
        if labels and {"kind", "category", "params"} <= value.keys():
            try:
                out["text"] = describe_rule(value, labels)
            except (KeyError, TypeError):
                pass
        return out
    return value


def envelope(request: Request, name: str, ctx: dict) -> dict:
    """The template's context as JSON: the same data the HTML page shows, for the Next.js frontend."""
    from fastapi.encoders import jsonable_encoder
    from between.web import present
    data = jsonable_encoder(ctx)
    labels = data.get("labels") or data.get("names") or {r: p.get("label") for r, p in (data.get("parents") or {}).items()}
    viewer = None
    with request.app.state.engine.connect() as conn:  # who is signed in, so every screen can say so
        if s := current_session(request, conn):
            import sqlalchemy as sa
            from between import db
            people = {r.role: r for r in conn.execute(sa.select(db.parent).where(db.parent.c.family_id == s.family_id))}
            viewer = {"fid": s.family_id, "role": s.role, "names": {r: p.label for r, p in people.items()},
                      "me": people[s.role].display_name if s.role in people else None}
    return {"template": name.removesuffix(".html"), "demo_mode": request.app.state.settings.demo_mode, "viewer": viewer,
            "words": {"categories": present.CATEGORY_NAMES, "status": present.STATUS_WORDS, "reason": present.REASON_WORDS},
            "ctx": _annotate(data, labels)}


def render(request: Request, name: str, status: int = 200, **ctx):
    if wants_json(request):
        from fastapi.responses import JSONResponse
        return JSONResponse(envelope(request, name, ctx), status_code=status)
    return request.app.state.templates.TemplateResponse(request, name, ctx, status_code=status)
