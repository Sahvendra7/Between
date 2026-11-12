"""Review the rules, answer questions privately, approve the exact version."""
from __future__ import annotations

import json
import re

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from between import db, ruleset as RS
from between.agreement import pages
from between.web.present import describe_rule
from between.web.deps import actor, checked_form, get_conn, now, render, require_family
from between.web.routes_family import labels

router = APIRouter()


def _own_ruleset(conn, fid, rsid):
    row = conn.execute(sa.select(db.ruleset.c.family_id).where(db.ruleset.c.id == rsid)).first()
    if row is None or row.family_id != fid:
        raise HTTPException(status_code=404)


def _split_on_quote(page_text: str, quote: str) -> tuple[str, str, str] | None:
    """(before, quote as written in the agreement, after); whitespace may differ from the stored quote."""
    words = quote.split()
    m = re.search(r"\s+".join(map(re.escape, words)), page_text) if words else None
    return (page_text[:m.start()], m.group(0), page_text[m.end():]) if m else None


@router.get("/f/{fid}/source")
def source(request: Request, fid: str, rs: str, r: str, conn=Depends(get_conn)):
    """The agreement as uploaded, at the cited page, with the rule's quote highlighted."""
    s = require_family(request, conn, fid)
    row = conn.execute(sa.select(db.ruleset).where(db.ruleset.c.id == rs, db.ruleset.c.family_id == fid)).mappings().first()
    rule = next((x for x in json.loads(row["json"])["rules"] if x["id"] == r and x.get("origin") == "agreement"), None) if row else None
    if rule is None:
        raise HTTPException(status_code=404)
    text = conn.execute(sa.select(db.agreement.c.text).where(db.agreement.c.id == row["agreement_id"])).scalar_one()
    names = labels(conn, fid)
    shown = []
    for n, lines in sorted(pages(text).items()):
        body = "\n".join(lines).strip("\n")
        parts = _split_on_quote(body, rule["source"]["quote"]) if n == rule["source"]["page"] else None
        shown.append({"n": n, "body": body, "parts": parts})
    return render(request, "source.html", s=s, fid=fid, rule=rule, what=describe_rule(rule, names), pages=shown)


@router.get("/f/{fid}/rules")
def rules_page(request: Request, fid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    rs, approvals = RS.current(conn, fid)
    if rs is None:
        return RedirectResponse(f"/f/{fid}/agreement", status_code=303)
    names = labels(conn, fid)
    resolved = {r["source"].get("question_id"): r["id"] for r in rs["rules"] if r.get("origin") == "resolution"}
    questions = []
    for q in rs["questions"]:
        questions.append({"q": q, "options": RS.options_for(q, rs["rules"]), "resolved_by": resolved.get(q["id"]),
                          "answers": RS.answers_for(conn, rs["id"], q["id"], s.role)})
    other = "B" if s.role == "A" else "A"
    return render(request, "rules.html", s=s, fid=fid, rs=rs, labels=names, other=other, approvals=approvals,
                  agreement_rules=[r for r in rs["rules"] if r.get("origin") == "agreement"],
                  resolutions=[r for r in rs["rules"] if r.get("origin") == "resolution"], questions=questions)


@router.post("/f/{fid}/rules/{rsid}/approve")
async def approve(request: Request, fid: str, rsid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    form = await checked_form(request, s)
    _own_ruleset(conn, fid, rsid)
    try:
        RS.approve(conn, rsid, s.role, form.get("hash_seen", ""), actor(s), now=now())
    except RS.RulesetError:
        raise HTTPException(status_code=409, detail="The rules changed since you opened this page. Reload and review them again.")
    return RedirectResponse(f"/f/{fid}/rules", status_code=303)


@router.post("/f/{fid}/questions/{qid}/answer")
async def answer(request: Request, fid: str, qid: str, conn=Depends(get_conn)):
    s = require_family(request, conn, fid)
    form = await checked_form(request, s)
    rsid = form.get("ruleset_id", "")
    _own_ruleset(conn, fid, rsid)
    t = now()
    try:
        RS.submit_answer(conn, rsid, qid, s.role, form.get("choice", ""), form.get("value") or None, actor(s), now=t)
    except RS.RulesetError as e:
        raise HTTPException(status_code=400, detail={"locked": "You've both answered this already.",
                                                     "bad_value": "Enter a number of days between 1 and 365."}.get(e.code, "That answer isn't one of the options."))
    RS.resolve_if_agreed(conn, fid, rsid, actor(s), now=t)
    return RedirectResponse(f"/f/{fid}/rules", status_code=303)
