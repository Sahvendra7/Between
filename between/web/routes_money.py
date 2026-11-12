"""Money & Time: the family's year on one screen (AG Studio report + Bryntum calendar), from one authorised feed."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from between import demo
from between.web.deps import checked_form, get_conn, now, require_family
from between.web.ledger import family_feed

router = APIRouter()


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
