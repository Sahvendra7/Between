"""Upload an agreement → the AI proposes rules → the validator grounds them → a rule-set version."""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from between import db, demo, ruleset as RS, validate as V
from between.agreement import AgreementError, pdf_to_text
from between.extraction import AIUnavailable, extract_rules
from between.web.deps import actor, checked_form, get_conn, now, render, require_family
from between.web.routes_family import labels

router = APIRouter()
SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "agreements"
SAMPLE_NAMES = {"plan1": "plan1_rivera_okafor.txt", "plan2": "plan2_crossborder.txt", "plan3": "plan3_mediated_memo.txt"}
AGREEMENT_ERRORS = {"no_text_layer": "This PDF has no text layer (it looks scanned). Upload a text PDF or paste the text.",
                    "not_a_pdf": "That file isn't a readable PDF."}


@router.get("/f/{fid}/agreement")
def agreement_form(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    return render(request, "agreement.html", s=s, fid=fid, labels=labels(conn, fid), samples=SAMPLE_NAMES)


async def _text_from(form, settings) -> str:
    if (name := form.get("sample")) in SAMPLE_NAMES:
        return (SAMPLES / SAMPLE_NAMES[name]).read_text()
    upload = form.get("file")
    if upload is not None and getattr(upload, "filename", ""):
        data = await upload.read()
        demo.check_upload(upload.content_type, len(data), settings)
        return pdf_to_text(data) if upload.content_type == "application/pdf" else data.decode("utf-8", errors="replace")
    return form.get("text") or ""


@router.post("/f/{fid}/agreement")
async def upload_agreement(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    form = await checked_form(request, s)
    settings, names = request.app.state.settings, labels(conn, fid)
    ctx = dict(s=s, fid=fid, labels=names, samples=SAMPLE_NAMES)
    try:
        text = await _text_from(form, settings)
        demo.check_agreement_text(text, settings)
    except demo.DemoGuard as g:
        return render(request, "agreement.html", 400, error=g.message, **ctx)
    except AgreementError as e:
        return render(request, "agreement.html", 400, error=AGREEMENT_ERRORS[e.code], **ctx)
    try:
        raw = extract_rules(text, names, client=request.app.state.ai)
    except AIUnavailable:
        return render(request, "agreement.html", 503, error="The AI couldn't read this agreement right now, so nothing was changed. "
                      "Try again in a minute.", **ctx)
    validated = V.validate(raw, text, names)
    t, aid = now(), uuid.uuid4().hex[:12]
    conn.execute(sa.insert(db.agreement).values(id=aid, family_id=fid, sha256=hashlib.sha256(text.encode()).hexdigest(),
                                                text=text, uploaded_by=s.role, uploaded_at=t))
    RS.create_version(conn, fid, aid, validated, names, actor(s), now=t)
    return RedirectResponse(f"/f/{fid}/rules", status_code=303)
