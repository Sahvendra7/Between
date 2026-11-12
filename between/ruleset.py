"""Rule-set versions, two-parent approval, private answers and operational resolutions (spec r2 §6).

A resolution is a working arrangement the parents agreed in Between to fill an open question.
It never changes the legal agreement and never overrides an agreement rule.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa

from between import db, record
from between.engine import ruleset_hash
from between.validate import check_resolution

__all__ = ["RulesetError", "ruleset_hash", "create_version", "approve", "current", "options_for",
           "submit_answer", "answers_for", "resolve_if_agreed"]


class RulesetError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _now(now):
    return now or datetime.now(timezone.utc)


def _row(conn, ruleset_id):
    row = conn.execute(sa.select(db.ruleset).where(db.ruleset.c.id == ruleset_id)).mappings().first()
    if row is None:
        raise RulesetError("unknown_ruleset")
    return row


def _latest_version(conn, family_id) -> int:
    return conn.execute(sa.select(sa.func.max(db.ruleset.c.version)).where(db.ruleset.c.family_id == family_id)).scalar() or 0


FEE_QUESTION = {"id": "q_fee", "type": "fee_policy", "affects": "fee_policy", "category": "*",
                "question": "PayPal charges the receiving parent a fee on each payment. Who should cover it?",
                "source": {"page": None, "section": "Between setting (not in your agreement)"}}


def create_version(conn, family_id: str, agreement_id: str, validated: dict, parties: dict, actor, now=None) -> dict:
    now = _now(now)
    questions = list(validated.get("questions", []))
    if not any(q.get("id") == FEE_QUESTION["id"] for q in questions):
        questions.append(dict(FEE_QUESTION))
    doc = {"parties": parties, "rules": validated["rules"], "questions": questions,
           "refused": validated.get("refused", [])}
    h = ruleset_hash(doc)
    rid, version = uuid.uuid4().hex[:12], _latest_version(conn, family_id) + 1
    conn.execute(sa.insert(db.ruleset).values(id=rid, family_id=family_id, agreement_id=agreement_id, version=version,
                                              json=json.dumps(doc), hash=h, created_at=now))
    record.append(conn, family_id, "ruleset.created", {
        "ruleset_id": rid, "version": version, "hash": h, "rules": len(doc["rules"]), "questions": len(doc["questions"]),
        "resolutions": [r["id"] for r in doc["rules"] if r.get("origin") == "resolution"]}, actor, now=now)
    return {"id": rid, "version": version, "hash": h, "json": doc}


def approve(conn, ruleset_id: str, role: str, hash_seen: str, actor, now=None) -> None:
    now, row = _now(now), _row(conn, ruleset_id)
    if row["version"] != _latest_version(conn, row["family_id"]):
        raise RulesetError("not_latest")
    if hash_seen != row["hash"]:
        raise RulesetError("stale_version")
    conn.execute(sa.delete(db.approval).where(db.approval.c.ruleset_id == ruleset_id, db.approval.c.role == role))
    conn.execute(sa.insert(db.approval).values(ruleset_id=ruleset_id, role=role, hash=row["hash"], at=now))
    record.append(conn, row["family_id"], "ruleset.approved",
                  {"ruleset_id": ruleset_id, "version": row["version"], "role": role, "hash": row["hash"]}, actor, now=now)


def current(conn, family_id: str) -> tuple[dict | None, dict[str, str]]:
    row = conn.execute(sa.select(db.ruleset).where(db.ruleset.c.family_id == family_id)
                       .order_by(db.ruleset.c.version.desc()).limit(1)).mappings().first()
    if row is None:
        return None, {}
    approvals = {a.role: a.hash for a in conn.execute(
        sa.select(db.approval).where(db.approval.c.ruleset_id == row["id"], db.approval.c.hash == row["hash"]))}
    return {**json.loads(row["json"]), "id": row["id"], "version": row["version"], "hash": row["hash"]}, approvals


def options_for(question: dict, rules: list[dict]) -> list[dict]:
    """Deterministic answer choices per question type. The AI never writes options."""
    opts = []
    kind, cat = question.get("affects"), question.get("category")
    if question.get("type") == "fee_policy":
        return [{"choice": c, "label": label, "makes_rule": {"kind": "fee_policy", "category": "*", "params": {"payer_adds": adds}},
                 "needs_value": False}
                for c, label, adds in (("receiver", "The receiving parent bears PayPal's fee", False),
                                       ("payer", "The paying parent adds the estimated fee", True))]
    if question.get("type") == "contradiction":
        for i, (params, src) in enumerate(zip(question.get("conflict_params", []), question.get("conflict_sources", []))):
            opts.append({"choice": f"use_{i}", "label": f"Use {src.get('section')} (page {src.get('page')})",
                         "makes_rule": {"kind": kind, "category": cat, "params": params}, "needs_value": False})
    elif question.get("type") == "undefined_term":
        base = next((r for r in rules if r.get("origin") == "agreement" and r["kind"] == kind and r["category"] == cat), None)
        if base:
            opts.append({"choice": "all_count", "label": f"Every {cat.replace('_', ' ')} cost counts under this clause",
                         "makes_rule": {"kind": kind, "category": cat, "params": base["params"]}, "needs_value": False})
    elif question.get("type") == "missing_number" and kind in ("request_deadline_days", "payment_deadline_days"):
        opts.append({"choice": "days", "label": "Agree a number of days", "makes_rule": {"kind": kind, "category": cat, "params": {}},
                     "needs_value": True})
    opts.append({"choice": "together", "label": "Decide each expense together", "makes_rule": None, "needs_value": False})
    return opts


def _question(doc, question_id):
    q = next((q for q in doc["questions"] if q.get("id") == question_id), None)
    if q is None:
        raise RulesetError("unknown_question")
    return q


def _answers(conn, ruleset_id, question_id) -> dict:
    rows = conn.execute(sa.select(db.answer).where(db.answer.c.ruleset_id == ruleset_id,
                                                   db.answer.c.question_id == question_id)).mappings()
    return {r["role"]: {"choice": r["choice"], "value": r["value"]} for r in rows}


def submit_answer(conn, ruleset_id: str, question_id: str, role: str, choice: str, value: str | None, actor, now=None) -> None:
    now, row = _now(now), _row(conn, ruleset_id)
    doc = json.loads(row["json"])
    q = _question(doc, question_id)
    opt = next((o for o in options_for(q, doc["rules"]) if o["choice"] == choice), None)
    if opt is None:
        raise RulesetError("bad_choice")
    if opt["needs_value"]:
        if not (value or "").isdigit() or not 1 <= int(value) <= 365:
            raise RulesetError("bad_value")
        value = str(int(value))
    else:
        value = None
    existing = _answers(conn, ruleset_id, question_id)
    if len(existing) == 2:
        raise RulesetError("locked")
    conn.execute(sa.delete(db.answer).where(db.answer.c.ruleset_id == ruleset_id, db.answer.c.question_id == question_id,
                                            db.answer.c.role == role))
    conn.execute(sa.insert(db.answer).values(ruleset_id=ruleset_id, question_id=question_id, role=role, choice=choice,
                                             value=value, at=now))
    record.append(conn, row["family_id"], "question.answered", {"ruleset_id": ruleset_id, "question_id": question_id,
                                                                "role": role}, actor, now=now)


def answers_for(conn, ruleset_id: str, question_id: str, viewer_role: str) -> dict:
    """The viewer's own answer always; the other parent's only once both have answered."""
    got = _answers(conn, ruleset_id, question_id)
    both = len(got) == 2
    other = "B" if viewer_role == "A" else "A"
    return {"mine": got.get(viewer_role), "other": got.get(other) if both else None, "both_answered": both}


def resolve_if_agreed(conn, family_id: str, ruleset_id: str, actor, now=None) -> dict | None:
    now, row = _now(now), _row(conn, ruleset_id)
    doc = json.loads(row["json"])
    resolved = {r["source"].get("question_id") for r in doc["rules"] if r.get("origin") == "resolution"}
    n = len([r for r in doc["rules"] if r.get("origin") == "resolution"])
    new = []
    for q in doc["questions"]:
        if q["id"] in resolved:
            continue
        got = _answers(conn, ruleset_id, q["id"])
        if len(got) != 2 or got["A"] != got["B"]:
            continue
        opt = next((o for o in options_for(q, doc["rules"]) if o["choice"] == got["A"]["choice"]), None)
        if not opt or not opt["makes_rule"]:
            continue
        made = json.loads(json.dumps(opt["makes_rule"]))
        if opt["needs_value"]:
            made["params"] = {"days": int(got["A"]["value"])}
        n += 1
        rule = {"id": f"R{n}", "origin": "resolution", **made,
                "source": {"question_id": q["id"], "answered_by": ["A", "B"], "answered_at": now.isoformat()}}
        if check_resolution(rule, doc["questions"]) is None:
            new.append(rule)
    if not new:
        return None
    v = create_version(conn, family_id, row["agreement_id"],
                       {"rules": doc["rules"] + new, "questions": doc["questions"], "refused": doc.get("refused", [])},
                       doc["parties"], actor, now=now)
    done = {r["source"]["question_id"] for r in new} | resolved
    for a in conn.execute(sa.select(db.answer).where(db.answer.c.ruleset_id == ruleset_id)).mappings().all():
        if a["question_id"] not in done:  # carry open disagreements forward instead of losing them
            conn.execute(sa.insert(db.answer).values(**{**dict(a), "ruleset_id": v["id"]}))
    return v
