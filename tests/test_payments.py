import json
from pathlib import Path

import httpx
import pytest

from between import payments as P

FX = Path(__file__).parent / "fixtures" / "paypal"


def fx(name):
    return json.loads((FX / f"{name}.json").read_text())


def client(routes):
    """routes: {(method, path): (status, body)}; records every request."""
    seen = []

    def handler(req: httpx.Request):
        seen.append(req)
        if req.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "T", "expires_in": 32400})
        status, body = routes[(req.method, req.url.path)]
        return httpx.Response(status, json=body)

    pp = P.PayPal("id", "secret", http=httpx.Client(transport=httpx.MockTransport(handler)))
    return pp, seen


def test_base_url_is_sandbox_only():
    assert P.BASE == "https://api-m.sandbox.paypal.com"


def test_create_order_sends_payee_and_request_id():
    pp, seen = client({("POST", "/v2/checkout/orders"): (200, fx("create_order"))})
    out = pp.create_order(25200, "sb-a@personal.example.com", "exp_e1", "pay_p1",
                          "https://b/pay/return?p=p1", "https://b/pay/cancel?p=p1", "pay_p1_create")
    req = seen[-1]
    body = json.loads(req.content)
    pu = body["purchase_units"][0]
    assert body["intent"] == "CAPTURE" and pu["payee"] == {"email_address": "sb-a@personal.example.com"}
    assert pu["amount"] == {"currency_code": "USD", "value": "252.00"} and pu["custom_id"] == "exp_e1"
    assert req.headers["PayPal-Request-Id"] == "pay_p1_create"
    assert out == {"id": "5H058147FB671984G", "approve_url": "https://www.sandbox.paypal.com/checkoutnow?token=5H058147FB671984G"}


def test_capture_already_captured_raises_specific_issue():
    pp, _ = client({("POST", "/v2/checkout/orders/O1/capture"): (422, fx("capture_order_already"))})
    with pytest.raises(P.PayPalError) as e:
        pp.capture_order("O1", "pay_p1_capture")
    assert e.value.status == 422 and e.value.issue == P.ALREADY_CAPTURED


def test_refund_is_not_offered():
    assert not any(hasattr(P.PayPal, n) for n in ("refund", "refund_capture", "void", "authorize", "payout"))


def test_verify_webhook_true_only_on_success():
    ok, _ = client({("POST", "/v1/notifications/verify-webhook-signature"): (200, {"verification_status": "SUCCESS"})})
    bad, _ = client({("POST", "/v1/notifications/verify-webhook-signature"): (200, {"verification_status": "FAILURE"})})
    hook = fx("webhook_capture_completed")
    assert ok.verify_webhook(hook["headers"], hook["event"], "WH1") is True
    assert bad.verify_webhook(hook["headers"], hook["event"], "WH1") is False


def test_token_is_cached():
    pp, seen = client({("GET", "/v2/payments/captures/C1"): (200, fx("get_capture_completed"))})
    pp.get_capture("C1"); pp.get_capture("C1")
    assert sum(r.url.path == "/v1/oauth2/token" for r in seen) == 1
