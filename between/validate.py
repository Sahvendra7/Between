"""Grounding: what the model proposed must be in the agreement, word for word, in the right place.

Contradictions and undefined words become questions for both parents, never a pick.
"""
from __future__ import annotations

import json
import re

from between.agreement import label_key, locate, norm

CATEGORIES = {"medical", "extracurricular", "education", "childcare", "camp", "travel_child",
              "travel_parent", "clothing", "gifts", "food", "school_supplies", "*"}
PARAMS = {"split": {"shares"}, "consent_required": {"over_minor"}, "emergency_exception": {"notify_hours"},
          "annual_cap": {"per_parent_minor"}, "covers_first": {"party", "up_to_minor"},
          "request_deadline_days": {"days"}, "payment_deadline_days": {"days"},
          "not_shared": set(), "receipt_required": set()}
PARTIES = ("A", "B")
VAGUE = re.compile(r"\b(reasonable|reasonably|promptly|appropriate|necessary|significant|substantial|as soon as possible)\b", re.I)
DEADLINES = {"request_deadline_days", "payment_deadline_days"}


def _has_number(quote: str, n: int) -> bool:
    plain = re.sub(r"(?<=\d),(?=\d{3})", "", quote)
    return re.search(rf"(?<![\d.]){n}(?![\d])", plain) is not None


def _share_bound(quote: str, pct: int, mine: str, other: str) -> bool:
    for seg in re.split(r",|;| and ", quote.lower()):
        if re.search(rf"\b{pct}\s*%", seg) and mine.lower() in seg and other.lower() not in seg:
            return True
    return False


def _check_shape(rule: dict) -> str | None:
    kind, cat, params = rule.get("kind"), rule.get("category"), rule.get("params", {})
    if kind not in PARAMS:
        return "unknown_kind"
    if cat not in CATEGORIES:
        return "unknown_category"
    if not isinstance(params, dict) or set(params) != PARAMS[kind]:
        return "bad_params"
    for key in ("over_minor", "per_parent_minor", "up_to_minor", "days", "notify_hours"):
        if key in params and (not isinstance(params[key], int) or isinstance(params[key], bool) or params[key] <= 0):
            return "bad_number"
    if kind == "covers_first" and params["party"] not in PARTIES:
        return "bad_party"
    if kind == "split":
        shares = params["shares"]
        if not isinstance(shares, dict) or set(shares) != set(PARTIES) or not all(
                isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100 for v in shares.values()):
            return "bad_shares"
        if sum(shares.values()) != 100:
            return "shares_not_100"
    return None


def check_rule(rule: dict, text: str, parties: dict[str, str]) -> str | None:
    """A refusal code, or None when the agreement rule is grounded in the text."""
    if code := _check_shape(rule):
        return code
    params, src = rule["params"], rule.get("source", {})
    quote = src.get("quote", "") or ""
    if "..." in quote or "…" in quote:
        return "quote_not_contiguous"
    page = src.get("page")
    labels = locate(text, quote, page) if isinstance(page, int) else None
    if labels is None:
        return "quote_not_on_page"
    if label_key(str(src.get("section", ""))) not in labels:
        return "wrong_section"
    for key in ("over_minor", "per_parent_minor", "up_to_minor"):
        if key in params and (params[key] % 100 or not _has_number(quote, params[key] // 100)):
            return "amount_not_in_quote"
    for key in ("days", "notify_hours"):
        if key in params and not _has_number(quote, params[key]):
            return "number_not_in_quote"
    if rule["kind"] == "split":
        shares = params["shares"]
        if shares["A"] == shares["B"]:
            if not re.search(r"equal|50/50|50 ?%", quote, re.I):
                return "equal_split_not_in_quote"
        elif not all(_share_bound(quote, shares[p], parties[p], parties[o]) for p, o in (("A", "B"), ("B", "A"))):
            return "share_party_unclear"
    return None


def check_resolution(rule: dict, questions: list[dict]) -> str | None:
    """Resolutions answer an open question; they have no quote, so only shape and target are checked."""
    src = rule.get("source", {})
    q = next((q for q in questions if q.get("id") == src.get("question_id")), None)
    if q is None:
        return "no_such_question"
    if sorted(src.get("answered_by", [])) != ["A", "B"]:
        return "not_agreed_by_both"
    if rule.get("category") != q.get("category") and q.get("category") != "*":
        return "category_mismatch"
    if rule.get("kind") == "fee_policy":
        return None if rule.get("params") in ({"payer_adds": True}, {"payer_adds": False}) else "bad_params"
    return _check_shape(rule)


def _question_type(q: dict) -> str:
    if q.get("conflict"):
        return "contradiction"
    vague = VAGUE.search(q.get("source", {}).get("quote", "") or "")
    if vague and q.get("affects") in DEADLINES:
        return "missing_number"
    if vague:
        return "undefined_term"
    return "model_flagged"


def validate(extracted: dict, text: str, parties: dict[str, str]) -> dict:
    """Split the model's output into grounded agreement rules, refused rules and questions."""
    accepted, refused = [], []
    for i, rule in enumerate(extracted.get("rules", [])):
        rule = {**rule, "id": rule.get("id") or f"r{i + 1}", "origin": "agreement"}
        code = check_rule(rule, text, parties)
        (refused if code else accepted).append({**rule, "refusal": code} if code else rule)
    questions = []
    for amb in extracted.get("ambiguities", []):
        src = amb.get("source", {})
        grounded = isinstance(src.get("page"), int) and locate(text, src.get("quote", ""), src["page"]) is not None
        questions.append({k: amb.get(k) for k in ("category", "affects", "question", "source")} | {"grounded": grounded})
    for r in accepted:  # an undefined qualifier always becomes a question, whatever the model thought
        if m := VAGUE.search(r["source"]["quote"]):
            if not any(q.get("category") == r["category"] and q.get("affects") == r["kind"] for q in questions):
                questions.append({"category": r["category"], "affects": r["kind"], "grounded": True, "auto": m.group(0),
                                  "question": f"'{m.group(0)}' isn't defined. What does it cover?", "source": r["source"]})
    by_key: dict[tuple, list] = {}
    for r in accepted:
        by_key.setdefault((r["kind"], r["category"]), []).append(r)
    for (kind, cat), group in by_key.items():
        if len({json.dumps(r["params"], sort_keys=True) for r in group}) > 1:
            for r in group:
                accepted.remove(r)
            questions.append({"category": cat, "affects": kind, "grounded": True, "conflict": [r["id"] for r in group],
                              "conflict_sources": [r["source"] for r in group], "conflict_params": [r["params"] for r in group],
                              "question": f"The agreement says different things about {kind.replace('_', ' ')} for {cat}.",
                              "source": group[0]["source"]})
    # One question per (category, kind): a contradiction absorbs the model's own flag on the same thing.
    contradicted = {(q["category"], q["affects"]) for q in questions if q.get("conflict")}
    questions = [q for q in questions if q.get("conflict") or (q.get("category"), q.get("affects")) not in contradicted]
    questions.sort(key=lambda q: 0 if q.get("conflict") else 1)
    for i, q in enumerate(questions, 1):
        q["id"] = f"q{i}"
        q["type"] = _question_type(q)
    return {"rules": accepted, "refused": refused, "questions": questions}


__all__ = ["CATEGORIES", "PARAMS", "check_rule", "check_resolution", "validate", "norm"]
