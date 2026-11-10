"""PayPal webhooks: verified with PayPal, deduplicated, and only ever a hint to re-read the payment.
A webhook never marks anything paid by itself."""
from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from between import db, record
from between.reconcile import complete_if_approved
from between.web.deps import get_conn, now

router = APIRouter()


@router.post("/webhooks/paypal")
async def paypal_webhook(request: Request, conn=Depends(get_conn)):
    try:
        event = await request.json()
    except ValueError:
        return JSONResponse({"error": "bad_json"}, status_code=400)
    pp, settings = request.app.state.pp, request.app.state.settings
    if pp is None:
        return JSONResponse({"error": "not_configured"}, status_code=503)
    if not isinstance(event, dict) or not pp.verify_webhook(dict(request.headers), event, settings.paypal_webhook_id):
        return JSONResponse({"error": "signature"}, status_code=400)
    etype, resource = event.get("event_type", ""), event.get("resource") or {}
    capture_id = resource.get("id") if etype.startswith("PAYMENT.CAPTURE") else None
    order_id = ((resource.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id") or \
        (resource.get("id") if etype.startswith("CHECKOUT.ORDER") else None)
    try:
        with conn.begin_nested():
            conn.execute(sa.insert(db.webhook_event).values(id=str(event.get("id")), type=etype, resource_id=resource.get("id"),
                                                            verified=True, received_at=now()))
    except IntegrityError:
        return {"ok": True, "duplicate": True}
    conds = [db.payment.c.capture_id == capture_id] if capture_id else []
    if order_id:
        conds.append(db.payment.c.order_id == order_id)
    row = conn.execute(sa.select(db.payment.c.id, db.payment.c.capture_id).where(sa.or_(*conds))).first() if conds else None
    if row is None:
        return {"ok": True, "matched": False}
    if capture_id and not row.capture_id:  # the GET below decides whether this capture is really ours
        conn.execute(sa.update(db.payment).where(db.payment.c.id == row.id).values(capture_id=capture_id))
    complete_if_approved(conn, pp, row.id, record.PAYPAL, now(), reversal_reported=etype == "PAYMENT.CAPTURE.REVERSED")
    return {"ok": True, "matched": True}
