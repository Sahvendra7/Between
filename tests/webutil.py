"""Helpers for web tests: an app on in-memory SQLite, a fake AI client, two parents' browsers."""
import copy
import re
from types import SimpleNamespace

from fastapi.testclient import TestClient

from between import db
from between.config import Settings
from between.extraction import Extraction
from between.web.app import create_app

A_EMAIL, B_EMAIL = "sb-mother@personal.example.com", "sb-father@personal.example.com"


def fake_ai(key, receipt_total=42000):
    """An AI client: rule extraction returns the hand-written key; the receipt reader returns receipt_total."""
    raw = {"rules": [{**{k: v for k, v in r.items() if k != "id"},
                      "params": {"shares": None, "over_minor": None, "notify_hours": None, "per_parent_minor": None,
                                 "party": None, "up_to_minor": None, "days": None, **copy.deepcopy(r["params"])}}
                     for r in key["rules"]],
           "ambiguities": copy.deepcopy(key["ambiguities"])}
    parsed = Extraction.model_validate(raw)
    from between.extraction import ReceiptGuess
    guess = ReceiptGuess(merchant="Bright Smiles Orthodontics", date="2026-10-01", total_minor=receipt_total)
    rules = lambda **kw: SimpleNamespace(stop_reason="end_turn", parsed_output=parsed if kw["output_format"] is Extraction else None)
    receipt = lambda **kw: SimpleNamespace(stop_reason="end_turn", parsed_output=guess)
    return SimpleNamespace(messages=SimpleNamespace(parse=receipt), beta=SimpleNamespace(messages=SimpleNamespace(parse=rules)))


def make(ai=None, pp=None, **settings):
    engine = db.make_engine("sqlite://")
    db.init_db(engine)
    s = Settings(**{"database_url": "sqlite://", "base_url": "http://testserver", "demo_mode": True, **settings})
    app = create_app(s, engine, ai=ai, pp=pp)
    return app, engine


def csrf(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def create_family(client, label="Mother", other="Father", name="Maria", email=A_EMAIL):
    r = client.post("/families", data={"role_label": label, "other_label": other, "display_name": name, "paypal_email": email})
    assert r.status_code == 200, r.text
    fid = re.search(r'data-family="([^"]+)"', r.text).group(1)
    token = re.search(r"/join/([A-Za-z0-9_\-]+)", r.text).group(1)
    return fid, token


def join(client, token, name="David", email=B_EMAIL):
    r = client.post(f"/join/{token}", data={"display_name": name, "paypal_email": email}, follow_redirects=False)
    return r


def two_parents(app, label="Mother", other="Father"):
    a, b = TestClient(app), TestClient(app)
    fid, token = create_family(a, label=label, other=other)
    assert join(b, token).status_code == 303
    return a, b, fid


def upload(client, fid, text):
    page = client.get(f"/f/{fid}/agreement").text
    return client.post(f"/f/{fid}/agreement", data={"csrf": csrf(page), "text": text}, follow_redirects=False)


def approve_rules(client, fid):
    page = client.get(f"/f/{fid}/rules").text
    rsid = re.search(r'action="/f/[^/]+/rules/([^/]+)/approve"', page).group(1)
    h = re.search(r'name="hash_seen" value="([0-9a-f]{64})"', page).group(1)
    return client.post(f"/f/{fid}/rules/{rsid}/approve", data={"csrf": csrf(page), "hash_seen": h}, follow_redirects=False)


def family_with_rules(app, doc_text):
    a, b, fid = two_parents(app)
    assert upload(a, fid, doc_text).status_code == 303
    assert approve_rules(a, fid).status_code == 303 and approve_rules(b, fid).status_code == 303
    return a, b, fid


def submit_expense(client, fid, category, receipt=b"\x89PNG synthetic receipt", amount=None, ctype="image/png", emergency=False):
    page = client.get(f"/f/{fid}/expenses/new").text
    data = {"csrf": csrf(page), "category": category}
    if emergency:
        data["emergency"] = "on"
    r = client.post(f"/f/{fid}/expenses/new", data=data, files={"receipt": ("receipt.png", receipt, ctype)})
    if r.status_code != 200:
        return r
    form = dict(re.findall(r'name="(category|incurred_on|receipt_sha256|emergency)" value="([^"]*)"', r.text))
    guess = re.search(r'name="amount" value="([^"]*)"', r.text).group(1)
    form.update(csrf=csrf(r.text), amount=amount if amount is not None else guess)
    return client.post(f"/f/{fid}/expenses/confirm", data=form, follow_redirects=False)


class FakePayPal:
    """Behaves like the sandbox did in the spike: idempotent create/capture, ALREADY_CAPTURED on repeats."""

    def __init__(self, capture_status="COMPLETED"):
        self.orders, self.calls, self.capture_status, self.webhook_ok = {}, [], capture_status, True

    def create_order(self, amount_minor, payee_email, custom_id, reference_id, return_url, cancel_url, request_id):
        self.calls.append(("create", request_id))
        oid = "O-" + reference_id
        self.orders.setdefault(oid, {"amount": amount_minor, "payee": payee_email, "custom_id": custom_id, "captured": False})
        return {"id": oid, "approve_url": f"https://www.sandbox.paypal.com/checkoutnow?token={oid}"}

    def _capture(self, oid):
        from between.money import fee_estimate
        o = self.orders[oid]
        fee = fee_estimate(o["amount"])
        v = lambda c: {"currency_code": "USD", "value": f"{c // 100}.{c % 100:02d}"}
        return {"id": "C-" + oid, "status": self.capture_status, "amount": v(o["amount"]), "custom_id": o["custom_id"],
                "payee": {"email_address": o["payee"]},
                "seller_receivable_breakdown": {"gross_amount": v(o["amount"]), "paypal_fee": v(fee), "net_amount": v(o["amount"] - fee)},
                "supplementary_data": {"related_ids": {"order_id": oid}}}

    def capture_order(self, order_id, request_id):
        from between.payments import ALREADY_CAPTURED, PayPalError
        self.calls.append(("capture", request_id))
        if self.orders[order_id]["captured"]:
            raise PayPalError(422, "UNPROCESSABLE_ENTITY", ALREADY_CAPTURED, "dbg")
        self.orders[order_id]["captured"] = True
        return {"id": order_id, "status": "COMPLETED", "purchase_units": [{"payments": {"captures": [self._capture(order_id)]}}]}

    def get_order(self, order_id):
        o = self.orders[order_id]
        caps = [self._capture(order_id)] if o["captured"] else []
        return {"id": order_id, "status": "COMPLETED" if caps else "APPROVED", "purchase_units": [{"payments": {"captures": caps}}]}

    def get_capture(self, capture_id):
        self.calls.append(("get_capture", capture_id))
        return self._capture(capture_id[2:])

    def verify_webhook(self, headers, event, webhook_id):
        return self.webhook_ok
