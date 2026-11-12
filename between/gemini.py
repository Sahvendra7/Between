"""Gemini backend, used when GEMINI_API_KEY is set (the owner's free-tier key; the Anthropic key has no credits).

It mimics the one slice of the Anthropic client Between calls (`messages.parse` and `beta.messages.parse`), so
the same prompts, the same Pydantic output schemas and the same fail-closed checks in extraction.py and
schedule.py apply unchanged. The model never decides anything: between.validate grounds every rule it proposes.
"""
from __future__ import annotations

import logging
import time
from types import SimpleNamespace

import httpx
from pydantic import BaseModel, ValidationError

URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
# Anthropic model id the call site asks for -> Gemini models tried in order, like Anthropic's server-side
# fallback. On the free tier gemini-3.8-flash mostly answered 503 or timed out (12 Nov), so it isn't used.
# 503 "high demand" is usually brief, so the primary is retried before falling back: the lite model misses rules
# in the mediated-memo sample (fails closed, but asks the parents more often).
MODELS = {"claude-sonnet-5-5": ("gemini-3.6-flash", "gemini-3.6-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"),
          "claude-haiku-5-5": ("gemini-3.5-flash-lite",)}
RETRYABLE = {408, 429, 500, 502, 503, 504}
log = logging.getLogger("between.ai")


class GeminiError(Exception):
    pass


def _parts(content) -> list[dict]:
    if isinstance(content, str):
        return [{"text": content}]
    out = []
    for block in content:
        if block["type"] == "text":
            out.append({"text": block["text"]})
        else:  # image or document, base64
            src = block["source"]
            out.append({"inlineData": {"mimeType": src["media_type"], "data": src["data"]}})
    return out


class _Messages:
    def __init__(self, key: str, timeout: float):
        self._headers, self._timeout = {"x-goog-api-key": key}, timeout

    def parse(self, *, model: str, messages: list[dict], output_format: type[BaseModel], system: str | None = None,
              max_tokens: int | None = None, **_ignored):
        body = {"contents": [{"role": "user", "parts": _parts(m["content"])} for m in messages],
                "generationConfig": {"responseMimeType": "application/json",
                                     "responseJsonSchema": output_format.model_json_schema()}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        last, slow = "no_model", set()
        for i, name in enumerate(MODELS[model]):
            if name in slow:  # don't wait out a timed-out model twice
                continue
            if i and name == MODELS[model][i - 1]:
                time.sleep(2 * i)  # back off before retrying the same model
            try:
                r = httpx.post(URL.format(name), headers=self._headers, json=body, timeout=self._timeout)
            except httpx.HTTPError as exc:
                last = type(exc).__name__
                if isinstance(exc, httpx.TimeoutException):
                    slow.add(name)
                continue
            if r.status_code in RETRYABLE:
                last = f"http_{r.status_code}"
                continue
            if r.status_code != 200:
                raise GeminiError(f"http_{r.status_code}")
            cand = (r.json().get("candidates") or [{}])[0]
            if cand.get("finishReason") not in ("STOP", None):  # SAFETY, RECITATION, MAX_TOKENS...: fail closed
                return SimpleNamespace(stop_reason="refusal", parsed_output=None)
            text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))
            log.info("gemini answered: model=%s skipped=%s", name, last if name != MODELS[model][0] else "-")
            try:
                return SimpleNamespace(stop_reason="end_turn", parsed_output=output_format.model_validate_json(text))
            except ValidationError:
                raise GeminiError("bad_json") from None
        raise GeminiError(last)


class Gemini:
    def __init__(self, api_key: str, timeout: float = 60.0):
        self.messages = _Messages(api_key, timeout)
        self.beta = SimpleNamespace(messages=self.messages)
