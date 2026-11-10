"""PayPal REST, sandbox only. One flow: an Orders v2 checkout (intent=CAPTURE) paying the other
parent's own PayPal account. Between never holds money, never refunds, voids, authorizes or pays out:
the spike showed it can't do those on a parent's account, and the product doesn't need them.
"""
from __future__ import annotations

import time
from collections.abc import Mapping

import httpx

BASE = "https://api-m.sandbox.paypal.com"  # no live mode exists in this codebase
ALREADY_CAPTURED = "ORDER_ALREADY_CAPTURED"


class PayPalError(Exception):
    def __init__(self, status: int, name: str, issue: str | None, debug_id: str | None):
        super().__init__(f"{status} {name} {issue or ''}".strip())
        self.status, self.name, self.issue, self.debug_id = status, name, issue, debug_id


def _usd(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


class PayPal:
    def __init__(self, client_id: str, client_secret: str, http: httpx.Client | None = None):
        self._id, self._secret = client_id, client_secret
        self._http = http or httpx.Client(timeout=30)
        self._token, self._expires = None, 0.0

    def _auth(self) -> str:
        if self._token and time.monotonic() < self._expires:
            return self._token
        r = self._http.post(f"{BASE}/v1/oauth2/token", data={"grant_type": "client_credentials"}, auth=(self._id, self._secret))
        if r.status_code != 200:
            raise PayPalError(r.status_code, "AUTHENTICATION_FAILURE", None, None)
        body = r.json()
        self._token, self._expires = body["access_token"], time.monotonic() + max(60, body.get("expires_in", 3600) - 60)
        return self._token

    def _call(self, method: str, path: str, body=None, request_id: str | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self._auth()}", "Content-Type": "application/json", "Prefer": "return=representation"}
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        r = self._http.request(method, f"{BASE}{path}", headers=headers, json=body)
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code >= 300:
            details = data.get("details") or [{}]
            raise PayPalError(r.status_code, data.get("name", "HTTP_ERROR"), details[0].get("issue"), data.get("debug_id"))
        return data

    def create_order(self, amount_minor: int, payee_email: str, custom_id: str, reference_id: str,
                     return_url: str, cancel_url: str, request_id: str) -> dict:
        body = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": reference_id, "custom_id": custom_id,
                "description": "Child expense share (Between, sandbox)",
                "amount": {"currency_code": "USD", "value": _usd(amount_minor)},
                "payee": {"email_address": payee_email},
            }],
            "payment_source": {"paypal": {"experience_context": {
                "brand_name": "Between (sandbox)", "shipping_preference": "NO_SHIPPING", "user_action": "PAY_NOW",
                "return_url": return_url, "cancel_url": cancel_url}}},
        }
        data = self._call("POST", "/v2/checkout/orders", body, request_id)
        approve = next(l["href"] for l in data.get("links", []) if l.get("rel") in ("payer-action", "approve"))
        return {"id": data["id"], "approve_url": approve}

    def capture_order(self, order_id: str, request_id: str) -> dict:
        return self._call("POST", f"/v2/checkout/orders/{order_id}/capture", {}, request_id)

    def get_order(self, order_id: str) -> dict:
        return self._call("GET", f"/v2/checkout/orders/{order_id}")

    def get_capture(self, capture_id: str) -> dict:
        return self._call("GET", f"/v2/payments/captures/{capture_id}")

    def verify_webhook(self, headers: Mapping[str, str], event: dict, webhook_id: str) -> bool:
        h = {k.lower(): v for k, v in headers.items()}
        body = {"auth_algo": h.get("paypal-auth-algo"), "cert_url": h.get("paypal-cert-url"),
                "transmission_id": h.get("paypal-transmission-id"), "transmission_sig": h.get("paypal-transmission-sig"),
                "transmission_time": h.get("paypal-transmission-time"), "webhook_id": webhook_id, "webhook_event": event}
        try:
            return self._call("POST", "/v1/notifications/verify-webhook-signature", body).get("verification_status") == "SUCCESS"
        except PayPalError:
            return False
