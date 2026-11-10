"""Turn the spike's recorded (already redacted) PayPal sandbox responses into test fixtures.

  uv run python scripts/make_fixtures.py

custom_id is rewritten to "exp_e1" so fixtures match the test expense id; synthetic variants
(refunded, partially refunded, pending) are marked "_synthetic": true.
"""
import copy
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPIKE = ROOT.parent / "spike" / "evidence"
OUT = ROOT / "tests" / "fixtures" / "paypal"


def first(step, status, pred=lambda b: True):
    for line in open(SPIKE / "paypal-log.jsonl"):
        e = json.loads(line)
        if e["step"] == step and e["response"]["status"] == status and pred(e["response"]["body"]):
            return copy.deepcopy(e["response"]["body"])
    raise SystemExit(f"missing {step} {status}")


def rewrite_custom(obj):
    s = json.dumps(obj).replace("expense-ortho-1", "exp_e1")
    return json.loads(s)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fx = {
        "create_order": first("create-order-capture", 200, lambda b: b.get("id") == "5H058147FB671984G"),
        "capture_order": first("capture-order", 201, lambda b: b.get("id") == "5H058147FB671984G"),
        "capture_order_already": first("capture-order", 422),
        "get_capture_completed": first("get-capture", 200, lambda b: b.get("id") == "38L069926Y258024J"),
        "get_order_completed": first("get-order", 200),
        "refund_403": first("refund-capture", 403),
        "verify_webhook_success": first("verify-webhook-signature", 200, lambda b: b.get("verification_status") == "SUCCESS"),
    }
    for name, status in (("refunded", "REFUNDED"), ("partially_refunded", "PARTIALLY_REFUNDED"), ("pending", "PENDING")):
        v = copy.deepcopy(fx["get_capture_completed"])
        v["status"], v["_synthetic"] = status, True
        fx[f"get_capture_{name}"] = v
    hook = json.load(open(sorted(glob.glob(str(SPIKE / "webhooks" / "*CAPTURE.COMPLETED.json")))[0]))
    fx["webhook_capture_completed"] = {"headers": hook["headers"], "event": hook["event"]}
    for name, body in fx.items():
        (OUT / f"{name}.json").write_text(json.dumps(rewrite_custom(body), indent=1))
        print("wrote", name)


if __name__ == "__main__":
    main()
