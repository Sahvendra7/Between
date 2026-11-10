"""Golden path over HTTP against a running Between (local or hosted), with a real PayPal sandbox approval.

  uv run python scripts/e2e_sandbox.py --base-url http://127.0.0.1:8000

Steps: demo family → both parents approve the sample rules → Mother submits the $420.00 sample
orthodontist receipt (amount confirmed as 420.00) → Father confirms and gets the PayPal sandbox
approval link → a person approves it as the paying parent's sandbox account (the script waits up to
10 minutes) → Between captures on return, verifies with PayPal → prints E2E PASS.
The script never enters PayPal credentials.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
RECEIPT = ROOT / "samples" / "receipts" / "ortho_420.png"


def csrf(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def step(msg):
    print(f"· {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--wait", type=int, default=600)
    base = ap.parse_args().base_url.rstrip("/")
    c = httpx.Client(base_url=base, timeout=60, follow_redirects=False)

    r = c.post("/demo/new")
    assert r.status_code == 303, r.text[:300]
    fid = r.headers["location"].rsplit("/", 1)[1]
    step(f"demo family {fid}")

    def approve():
        page = c.get(f"/f/{fid}/rules").text
        rsid = re.search(r'action="/f/[^/]+/rules/([^/]+)/approve"', page).group(1)
        h = re.search(r'name="hash_seen" value="([0-9a-f]{64})"', page).group(1)
        assert c.post(f"/f/{fid}/rules/{rsid}/approve", data={"csrf": csrf(page), "hash_seen": h}).status_code == 303

    def switch():
        assert c.post(f"/demo/switch/{fid}", data={"csrf": csrf(c.get(f"/f/{fid}").text)}).status_code == 303

    approve(); switch(); approve(); switch()
    step("rules approved by both parents")

    page = c.get(f"/f/{fid}/expenses/new").text
    r = c.post(f"/f/{fid}/expenses/new", data={"csrf": csrf(page), "category": "medical"},
               files={"receipt": ("ortho_420.png", RECEIPT.read_bytes(), "image/png")})
    assert r.status_code == 200, r.text[:300]
    form = dict(re.findall(r'name="(category|incurred_on|receipt_sha256|emergency)" value="([^"]*)"', r.text))
    form.update(csrf=csrf(r.text), amount="420.00")
    r = c.post(f"/f/{fid}/expenses/confirm", data=form)
    assert r.status_code in (303, 409), r.text[:300]
    if r.status_code == 409:
        print("This sample receipt was already used in this family; start a fresh run.")
        return 1
    loc = r.headers["location"]
    card = c.get(loc).text
    assert "$252.00" in card and "Father owes Mother" in card, "decision not as expected"
    step("expense decided: $252.00, Father owes Mother (§6.1, §7.2)")

    switch()
    page = c.get(loc + "/pay").text
    h = re.search(r'name="decision_hash" value="([0-9a-f]{64})"', page).group(1)
    r = c.post(loc + "/pay", data={"csrf": csrf(page), "confirm": "yes", "decision_hash": h})
    assert r.status_code == 303 and "sandbox.paypal.com" in r.headers["location"], r.text[:300]
    pid = None
    print("\nApprove this payment in a browser, logged in to PayPal sandbox as the PAYING parent's account:\n")
    print("   " + r.headers["location"] + "\n", flush=True)
    print("After approving, PayPal sends that browser to Between's return page, which captures the payment.")
    print("If PayPal shows you a different site, this script still finishes by asking PayPal directly.\n", flush=True)

    deadline = time.time() + ap.parse_args().wait
    while time.time() < deadline:
        card = c.get(loc).text
        if "Paid · verified with PayPal" in card:
            break
        rec = c.get(f"/f/{fid}/record").text
        c.post(f"/f/{fid}/record/verify", data={"csrf": csrf(rec)})
        time.sleep(10)
    rec = c.get(f"/f/{fid}/record").text
    ok = "Paid · verified with PayPal" in c.get(loc).text and "Record intact" in rec
    m = re.search(r'<td class="mono">([A-Z0-9]+)</td>', rec)
    step(f"capture {m.group(1) if m else '?'}; record {'intact' if 'Record intact' in rec else 'BROKEN'}")
    print("E2E PASS" if ok else "E2E FAIL (payment not verified in time)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
