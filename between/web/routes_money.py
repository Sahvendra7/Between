"""Money & Time: the family's year on one screen (AG Studio report + Bryntum calendar), from one authorised feed."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from between.web.deps import get_conn, now, require_family
from between.web.ledger import family_feed

router = APIRouter()


@router.get("/f/{fid}/money.json")
def money_json(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    return family_feed(conn, s, now().date())
