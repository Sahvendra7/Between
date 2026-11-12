"""Money & Time: the family's year on one screen (AG Studio report + Bryntum calendar), from one authorised feed."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from between import demo, engine as E, ruleset as RS
from between.web.deps import checked_form, get_conn, now, render, require_family
from between.web.ledger import family_feed

router = APIRouter()

# AG Studio (commercial, loaded from jsDelivr, pinned with SRI, never vendored) injects <style> tags, so this page
# alone allows inline styles. Scripts stay limited to this origin and the one pinned CDN file.
MONEY_CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
             "script-src 'self' https://cdn.jsdelivr.net; connect-src 'self'; form-action 'self'; "
             "frame-ancestors 'none'; base-uri 'none'")
AG_STUDIO_SRC = "https://cdn.jsdelivr.net/npm/ag-studio@3.1.0/dist/umd/ag-studio.min.js"
AG_STUDIO_SRI = "sha384-AQulWK/PF30iLAso56dIH/1+Iv852aUbFC98K7N1ZpLYVvmamIEAU36dEbUaPym1"


@router.get("/f/{fid}/money")
def money_page(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    settings = request.app.state.settings
    rs, approvals = RS.current(conn, fid)
    resp = render(request, "money.html", s=s, fid=fid, feed=family_feed(conn, s, now().date()),
                  approved=bool(rs and E.is_approved(rs, approvals)),
                  demo_family=settings.demo_mode and demo.is_visitor_family(conn, fid),
                  studio_src=AG_STUDIO_SRC, studio_sri=AG_STUDIO_SRI, license=settings.ag_studio_license)
    resp.headers["Content-Security-Policy"] = MONEY_CSP
    return resp


@router.get("/f/{fid}/money.json")
def money_json(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    return family_feed(conn, s, now().date())


@router.post("/f/{fid}/money/sample-year")
async def sample_year(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    await checked_form(request, s)
    try:
        demo.add_sample_year(conn, fid, s, now().date())
    except ValueError as e:
        code = str(e)
        detail = {"not_demo": "Sample years are only for demo families.",
                  "not_approved": "Approve your rules (both of you) first, so Between can decide each expense.",
                  "already_added": "This family already has its sample year."}[code]
        raise HTTPException(status_code=403 if code == "not_demo" else 409, detail=detail) from None
    return RedirectResponse(f"/f/{fid}/money", status_code=303)
