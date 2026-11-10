from types import SimpleNamespace

import anthropic
import httpx
import pytest

from between import extraction as X


class FakeParse:
    def __init__(self, parsed=None, stop_reason="end_turn", raise_exc=None):
        self.calls, self.parsed, self.stop_reason, self.raise_exc = [], parsed, stop_reason, raise_exc

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_exc:
            raise self.raise_exc
        return SimpleNamespace(stop_reason=self.stop_reason, parsed_output=self.parsed)


def fake_client(parse):
    return SimpleNamespace(messages=SimpleNamespace(parse=parse), beta=SimpleNamespace(messages=SimpleNamespace(parse=parse)))


GOOD = X.Extraction(rules=[X.ExtractedRule(kind="split", category="medical",
                                           params=X.Params(shares=X.Shares(A=40, B=60)),
                                           source=X.Source(quote="shall be paid 60% by the Father and 40% by the Mother", page=2, section="6.1"))],
                    ambiguities=[])
PARTIES = {"A": "Mother", "B": "Father"}


def test_request_has_no_sampling_params():
    parse = FakeParse(parsed=GOOD)
    X.extract_rules("doc", PARTIES, client=fake_client(parse))
    kw = parse.calls[0]
    assert not {"temperature", "top_p", "top_k"} & set(kw)
    assert kw["model"] == "claude-sonnet-5-5" and kw["max_tokens"] == 16000 and kw["output_format"] is X.Extraction
    assert "Mother" in kw["system"] and "Father" in kw["system"]


def test_rule_params_are_compacted_for_the_validator():
    out = X.extract_rules("doc", PARTIES, client=fake_client(FakeParse(parsed=GOOD)))
    assert out["rules"][0]["params"] == {"shares": {"A": 40, "B": 60}} and out["ambiguities"] == []


def test_refusal_fails_closed():
    with pytest.raises(X.AIUnavailable) as e:
        X.extract_rules("doc", PARTIES, client=fake_client(FakeParse(stop_reason="refusal")))
    assert e.value.code == "refusal"


def test_api_error_fails_closed():
    err = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    with pytest.raises(X.AIUnavailable) as e:
        X.extract_rules("doc", PARTIES, client=fake_client(FakeParse(raise_exc=err)))
    assert e.value.code == "api"


def test_missing_key_fails_closed():
    with pytest.raises(X.AIUnavailable) as e:
        X.extract_rules("doc", PARTIES, client=None)
    assert e.value.code == "no_key"


def test_receipt_uses_haiku_and_returns_guess():
    parse = FakeParse(parsed=X.ReceiptGuess(merchant="Bright Smiles", date="2026-10-01", total_minor=42000))
    g = X.read_receipt(b"\x89PNG fake", "image/png", client=fake_client(parse))
    kw = parse.calls[0]
    assert kw["model"] == "claude-haiku-5-5" and kw["max_tokens"] == 1024 and not {"temperature", "top_p", "top_k"} & set(kw)
    assert kw["messages"][0]["content"][0]["type"] == "image" and g.total_minor == 42000


def test_receipt_pdf_uses_document_block():
    parse = FakeParse(parsed=X.ReceiptGuess(merchant=None, date=None, total_minor=None))
    X.read_receipt(b"%PDF-1.4", "application/pdf", client=fake_client(parse))
    assert parse.calls[0]["messages"][0]["content"][0]["type"] == "document"
