# Build status (evidence)

## AI extraction gate on Gemini (Thu 12 Nov 2026, ~08:00 IST)
- The owner's Anthropic key has no credits ("credit balance is too low"), so the app uses the owner's free-plan Gemini key.
- `uv run python scripts/eval_extraction.py --runs 2 --backend sdk --workers 1` → 8/8 ok, `GATE PASS (sdk)`: plans 1–3 match every key rule and raise every expected question; plan 4 (planted instruction) accepted 0 injected rules.
- Served mostly by `gemini-3.6-flash`; some calls fell back to `gemini-3.5-flash-lite` after a 429. `gemini-3.8-flash` mostly answered 503 or timed out, so it isn't used.
- With 8 parallel requests the free plan returns 429s and the lite fallback misses the plan 3 memo's rules. Those failures are fail-closed: decisions went to "needs both parents", never a wrong amount, and no injected rule was accepted.
- Receipt `ortho_420.png` read as 42000 cents; plan 1 schedule grounded (alternate weeks, Sunday 18:00).

## Real sandbox run through the hosted app (Thu 12 Nov 2026, ~07:12 IST)
- Host: https://between-vjte.onrender.com (Render free web service + Render Postgres 16, Singapore), commit `3f3d350`.
- `uv run python scripts/e2e_sandbox.py --base-url https://between-vjte.onrender.com`:
  ```
  · demo family 6c261a79978f
  · rules approved by both parents
  · expense decided: $252.00, Father owes Mother (§6.1, §7.2)
  (Father's sandbox account approved the checkout on sandbox.paypal.com)
  · capture 17S84040MG287540N; record intact
  E2E PASS
  ```
- Read back independently from PayPal (`GET /v2/payments/captures/17S84040MG287540N`): `COMPLETED 252.00`, custom_id `exp_9432100bc6bf`, payee = Mother's sandbox account, fee 9.28, net 242.72.
- The browser that approved wasn't the script's session, so `/pay/return` correctly refused it (403); the payment completed through the PayPal read-back, as designed.
- PayPal sandbox webhook `9G731210DN4850140` delivered to `/webhooks/paypal`: `200 OK` at 01:42:29 UTC.

## Real sandbox run through the app, local (Wed 11 Nov 2026, ~04:00 IST)
- App: `uv run uvicorn between.web.app:app` on 127.0.0.1:8000, SQLite, `BETWEEN_DEMO_MODE=1`, no Anthropic key.
- Flow: "Try a demo family" → both parents approve 11 rules → Mother submits medical $420.00 (synthetic receipt, amount confirmed by hand because no AI key) → decision "$252.00, Father owes Mother, due 2026-11-24" citing §6.1 (p.2) and §7.2 (p.3) → Father confirms → PayPal sandbox checkout (Parent B approves) → Between captures and verifies.
- Result page: "Verified with PayPal": paid $252.00, fee $9.28 (from PayPal), received $242.72, capture `85D18309JT338721M`.
- Independent check:
  ```
  $ uv run python scripts/verify.py --family 87298f87639a
  pay_bc0efc8cea69 completed verified gross=25200 fee=928 net=24272 capture=85D18309JT338721M
  CHAIN OK
  exit=0
  ```
- Browser: desktop and 375px phone width checked; CSP console errors found (inline styles), fixed, pinned by `tests/test_templates.py`.

## Tests
- `uv run pytest -q` → 170 passed (after Tasks 15–16: corrections by reverse checkout, fee option).
- Extraction eval: `scripts/eval_extraction.py --runs 2 --backend cli` → GATE PASS (8/8 runs, incl. planted-instruction agreement). SDK eval pending `ANTHROPIC_API_KEY`.

## Golden-path e2e, local (Wed 11 Nov 2026, ~04:05 IST)
```
$ uv run python scripts/e2e_sandbox.py --base-url http://127.0.0.1:8000
· demo family d11f0d9689c8
· rules approved by both parents
· expense decided: $252.00, Father owes Mother (§6.1, §7.2)
  (approved in PayPal sandbox as Parent B; that browser had no Between session, so the return page refused it
   and the "approved but never returned" path captured it with the same idempotent request id)
· capture 0NV03348UR9558338; record intact
E2E PASS
```
Hosted e2e: pending Render deploy (owner).
