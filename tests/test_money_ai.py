"""The Ledger guide's proxy: AG Studio turns ⇄ Gemini chat completions, thought signatures kept, guarded and budgeted."""
import logging

from fastapi.testclient import TestClient

from between import money_ai as M
from test_ledger import approved_demo
from webutil import csrf, make

GEMINI_TOOL_CALL = {"id": "resp1", "created": 1794453182, "choices": [{"finish_reason": "tool_calls", "message": {
    "role": "assistant", "content": None,
    "tool_calls": [{"id": "call_1", "type": "function",
                    "function": {"name": "explain_expense", "arguments": "{\"expenseId\":\"e1\"}"},
                    "extra_content": {"google": {"thought_signature": "SIG"}}}]}}]}
GEMINI_TEXT = {"id": "resp2", "created": 1794453190, "choices": [{"finish_reason": "stop", "message": {
    "role": "assistant", "content": "Father owes $252.00 under §6.1 (page 2)."}}]}
USER = {"kind": "input", "type": "message", "role": "user", "status": "completed",
        "content": [{"type": "text", "text": "Why does Father owe $252?"}]}
TOOL = {"name": "explain_expense", "description": "The stored decision for one expense", "kind": "function",
        "parameters": {"type": "object", "additionalProperties": False, "$schema": "x",
                       "properties": {"expenseId": {"type": ["string", "null"]}}, "required": ["expenseId"]}}


def test_round_trip_keeps_signature():
    sigs = {}
    out = M.from_chat(GEMINI_TOOL_CALL, sigs)
    assert out["status"] == "completed"
    [call] = out["output"]
    assert (call["type"], call["callId"], call["name"], call["arguments"]) == ("function_call", "call_1", "explain_expense", "{\"expenseId\":\"e1\"}")
    req = {"instructions": "Be brief.", "tools": [TOOL], "toolChoice": "auto",
           "input": [USER, call, {"type": "function_call_output", "callId": "call_1", "output": "{\"cite\":[]}"}]}
    body = M.to_chat(req, sigs)
    assert body["model"] == M.MODEL and body["max_tokens"] == 2048
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user", "assistant", "tool"]
    tc = body["messages"][2]["tool_calls"][0]
    assert tc["id"] == "call_1" and tc["extra_content"]["google"]["thought_signature"] == "SIG"
    assert body["messages"][3] == {"role": "tool", "tool_call_id": "call_1", "content": "{\"cite\":[]}"}


def test_text_answer_becomes_message_item():
    out = M.from_chat(GEMINI_TEXT, {})
    [msg] = out["output"]
    assert msg["type"] == "message" and msg["role"] == "assistant"
    assert msg["content"][0] == {"type": "text", "text": "Father owes $252.00 under §6.1 (page 2).", "annotations": []}


def test_sanitize_strips_unsupported():
    s = M.sanitize(TOOL["parameters"])
    assert "additionalProperties" not in s and "$schema" not in s
    assert s["properties"]["expenseId"]["type"] == "string"
    assert M.sanitize({"anyOf": [{"type": "number"}, {"type": "null"}], "title": "x"}) == {"type": "number"}


def ai_app(**kw):
    app, engine = make(money_ai=True, gemini_api_key="test-key", **kw)
    return approved_demo(app, engine)


def ask(c, fid, body=None, token=True):
    headers = {"X-CSRF-Token": csrf(c.get(f"/f/{fid}/expenses/new").text)} if token else {}
    return c.post(f"/f/{fid}/money/ai", json=body or {"input": [USER], "instructions": "x", "tools": [TOOL]}, headers=headers)


def test_proxy_guards(monkeypatch):
    monkeypatch.setattr(M, "call_gemini", lambda body, key: (200, GEMINI_TEXT))
    app, engine = make(gemini_api_key="test-key")
    _, _, c, fid = approved_demo(app, engine)
    assert ask(c, fid).status_code == 404  # flag off
    app, engine, c, fid = ai_app()
    assert ask(c, fid, token=False).status_code == 403
    assert ask(c, fid, {"input": [USER], "instructions": "x" * 70_000}).status_code == 413
    for _ in range(M.HOURLY_LIMIT):
        assert ask(c, fid).json()["status"] == "completed"
    r = ask(c, fid)
    assert r.status_code == 429 and r.json()["status"] == "failed"


def test_proxy_upstream_failure_is_clean(monkeypatch):
    monkeypatch.setattr(M, "call_gemini", lambda body, key: (429, {"error": {"message": "quota"}}))
    app, engine, c, fid = ai_app()
    r = ask(c, fid)
    assert r.status_code == 200 and r.json()["status"] == "failed" and "quota" not in r.text


def test_proxy_logs_no_content(monkeypatch, caplog):
    monkeypatch.setattr(M, "call_gemini", lambda body, key: (200, GEMINI_TEXT))
    app, engine, c, fid = ai_app()
    with caplog.at_level(logging.DEBUG):
        ask(c, fid, {"input": [{**USER, "content": [{"type": "text", "text": "orthodontist bill"}]}], "instructions": "x"})
    assert not any("orthodontist" in r.getMessage() for r in caplog.records)


def test_model_call_runs_off_the_event_loop(monkeypatch):
    import asyncio
    seen = []

    def fake(body, key):
        try:
            asyncio.get_running_loop()
            seen.append("event loop")  # a slow model call here would freeze every other request
        except RuntimeError:
            seen.append("worker thread")
        return 200, GEMINI_TEXT
    monkeypatch.setattr(M, "call_gemini", fake)
    app, engine, c, fid = ai_app()
    assert ask(c, fid).json()["status"] == "completed" and seen == ["worker thread"]


def test_global_budget_caps_all_families_together(monkeypatch):
    monkeypatch.setattr(M, "call_gemini", lambda body, key: (200, GEMINI_TEXT))
    monkeypatch.setattr(M, "GLOBAL_HOURLY_LIMIT", 2)
    app, engine, c1, fid1 = ai_app()
    _, _, c2, fid2 = approved_demo(app, engine)
    assert ask(c1, fid1).json()["status"] == "completed"
    assert ask(c2, fid2).json()["status"] == "completed"
    r = ask(c2, fid2)  # a fresh demo family doesn't get a fresh budget
    assert r.status_code == 429 and r.json()["status"] == "failed"
