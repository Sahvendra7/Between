"""The Ledger guide's proxy: AG Studio agent turns ⇄ Gemini's OpenAI-compatible chat completions.

AG Studio's adapter contract is shaped like OpenAI's Responses API; Gemini's compatibility layer only offers chat
completions, so this module translates both ways. Gemini 3 tool calls carry a thought signature that must be sent
back on the next turn (a 400 otherwise), so signatures are kept per call id.

The model only explains: the agent's tools are read-only and return what Between's rules engine decided.
"""
from __future__ import annotations

import json
import time
from datetime import datetime

import httpx
import sqlalchemy as sa

from between import db

GEMINI_CHAT_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
MODEL = "gemini-3.5-flash-lite"  # gemini-3.6-flash was over its free quota on 12 Nov; lite handles tool calls
MAX_TOKENS = 2048
MAX_BODY = 65_536
HOURLY_LIMIT = 40
SIG_TTL = 3600
_DROP = {"$schema", "$id", "additionalProperties", "strict", "title"}


class SigCache(dict):
    """call id -> extra_content. shortcut: process memory on one Render instance; move to the DB to scale out."""

    def __init__(self):
        super().__init__()
        self._at: dict[str, float] = {}

    def __setitem__(self, key, value):
        now = time.monotonic()
        for k in [k for k, t in self._at.items() if now - t > SIG_TTL]:
            self._at.pop(k, None)
            self.pop(k, None)
        self._at[key] = now
        super().__setitem__(key, value)


SIGS = SigCache()


def sanitize(schema):
    """JSON Schema → the subset Gemini's compatibility layer accepts: no meta keys, nullable unions collapsed."""
    if isinstance(schema, list):
        return [sanitize(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: sanitize(v) for k, v in schema.items() if k not in _DROP}
    for key in ("anyOf", "oneOf"):
        if key in out:
            options = [o for o in out[key] if o.get("type") != "null"]
            if len(options) == 1:
                out.pop(key)
                out = {**options[0], **out}
    if isinstance(out.get("type"), list):
        types = [t for t in out["type"] if t != "null"]
        out["type"] = types[0] if len(types) == 1 else types
    if isinstance(out.get("properties"), dict):
        out["properties"] = {k: sanitize(v) for k, v in out["properties"].items()}
    return out


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") for p in content or [] if isinstance(p, dict))


def to_chat(req: dict, sigs: dict) -> dict:
    messages = [{"role": "system", "content": req["instructions"]}] if req.get("instructions") else []
    calls: list[dict] = []

    def flush():
        if calls:
            messages.append({"role": "assistant", "content": None, "tool_calls": list(calls)})
            calls.clear()

    for item in req.get("input", []):
        kind = item.get("type")
        if kind == "function_call":
            tc = {"id": item["callId"], "type": "function",
                  "function": {"name": item["name"], "arguments": item.get("arguments") or "{}"}}
            if item["callId"] in sigs:
                tc["extra_content"] = sigs[item["callId"]]
            calls.append(tc)
            continue
        flush()
        if kind == "function_call_output":
            out = item.get("output")
            messages.append({"role": "tool", "tool_call_id": item["callId"],
                             "content": out if isinstance(out, str) else json.dumps(out)})
        elif kind == "message" and item.get("role") in ("user", "assistant", "system"):
            role = "system" if item["role"] == "system" else item["role"]
            messages.append({"role": role, "content": _text(item.get("content"))})
    flush()
    body = {"model": MODEL, "max_tokens": MAX_TOKENS, "messages": messages}
    tools = [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                               "parameters": sanitize(t.get("parameters") or {"type": "object"})}}
             for t in req.get("tools") or [] if t.get("name")]
    if tools:
        body["tools"] = tools
        choice = req.get("toolChoice") or "auto"
        body["tool_choice"] = choice if isinstance(choice, str) else {"type": "function", "function": {"name": choice.get("name")}}
    fmt = req.get("responseFormat") or {}
    if fmt.get("type") in ("json", "json_schema") and fmt.get("schema"):
        body["response_format"] = {"type": "json_schema",
                                   "json_schema": {"name": fmt.get("name") or "answer", "schema": sanitize(fmt["schema"])}}
    return body


def from_chat(resp: dict, sigs: dict) -> dict:
    choice = (resp.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    rid = resp.get("id") or f"r{int(time.time() * 1000)}"
    output = []
    if msg.get("content"):
        output.append({"kind": "output", "type": "message", "role": "assistant", "id": f"msg_{rid}", "status": "completed",
                       "content": [{"type": "text", "text": msg["content"], "annotations": []}]})
    for tc in msg.get("tool_calls") or []:
        if tc.get("extra_content"):
            sigs[tc["id"]] = tc["extra_content"]
        output.append({"kind": "output", "type": "function_call", "id": f"fc_{tc['id']}", "callId": tc["id"],
                       "name": tc["function"]["name"], "arguments": tc["function"].get("arguments") or "{}",
                       "status": "completed"})
    status = "incomplete" if choice.get("finish_reason") == "length" else "completed"
    return {"id": rid, "createdAt": int(resp.get("created", time.time())) * 1000, "status": status, "output": output}


def failed(message: str) -> dict:
    return {"id": f"r{int(time.time() * 1000)}", "createdAt": int(time.time() * 1000), "status": "failed",
            "output": [], "error": {"message": message}}


def call_gemini(body: dict, key: str) -> tuple[int, dict | None]:
    try:
        r = httpx.post(GEMINI_CHAT_URL, json=body, timeout=60, headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError:
        return 599, None
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, None


def charge(conn, fid: str, now: datetime) -> bool:
    """One proxy call against this family's hourly budget. False once the hour's budget is spent."""
    hour = now.strftime("%Y-%m-%dT%H")
    t = db.ai_budget
    calls = conn.execute(sa.select(t.c.calls).where(t.c.family_id == fid, t.c.hour == hour)).scalar()
    if calls is None:
        conn.execute(sa.insert(t).values(family_id=fid, hour=hour, calls=1))
        return True
    if calls >= HOURLY_LIMIT:
        return False
    conn.execute(sa.update(t).where(t.c.family_id == fid, t.c.hour == hour).values(calls=calls + 1))
    return True
