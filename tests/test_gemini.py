"""Gemini adapter: falls back on overload, fails closed on blocks, bad JSON and outages."""
import json

import httpx
import pytest

from between import gemini as G
from between.extraction import AIUnavailable, Extraction, extract_rules

GOOD = {"rules": [], "ambiguities": []}


def reply(status, payload=None, finish="STOP"):
    body = {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": json.dumps(payload)}]}}]} if status == 200 else {}
    return httpx.Response(status, json=body)


@pytest.fixture
def calls(monkeypatch):
    seen, queue = [], []
    monkeypatch.setattr(G.time, "sleep", lambda s: None)

    def post(url, **kw):
        seen.append(url.split("/models/")[1].split(":")[0])
        r = queue.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(G.httpx, "post", post)
    return seen, queue


def parse(**kw):
    return G.Gemini("k").beta.messages.parse(model="claude-sonnet-5-5", messages=[{"role": "user", "content": "x"}],
                                            output_format=Extraction, system="s", **kw)


def test_overloaded_primary_is_retried_then_falls_back(calls):
    seen, queue = calls
    queue += [reply(503), reply(429), reply(503), reply(200, GOOD)]
    assert parse().parsed_output == Extraction(**GOOD)
    assert seen == ["gemini-3.6-flash"] * 3 + ["gemini-3.5-flash-lite"]


def test_timed_out_model_is_not_retried(calls):
    seen, queue = calls
    queue += [httpx.ReadTimeout("slow"), reply(200, GOOD)]
    parse()
    assert seen == ["gemini-3.6-flash", "gemini-3.5-flash-lite"]


def test_safety_block_is_a_refusal(calls):
    calls[1].append(reply(200, GOOD, finish="SAFETY"))
    r = parse()
    assert (r.stop_reason, r.parsed_output) == ("refusal", None)


def test_bad_json_and_outage_fail_closed(calls):
    seen, queue = calls
    queue.append(httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{nope"}]}}]}))
    with pytest.raises(AIUnavailable):
        extract_rules("text", {"A": "Mother", "B": "Father"}, client=G.Gemini("k"))
    queue += [reply(503)] * 4
    with pytest.raises(AIUnavailable):
        extract_rules("text", {"A": "Mother", "B": "Father"}, client=G.Gemini("k"))
