# Build status (evidence)

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
- `uv run pytest -q` → 148 passed.
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
