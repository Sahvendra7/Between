# Between

**Your co-parenting agreement, read once by AI, enforced by code on every child expense. The parent who owes pays the other parent's own PayPal account, and every payment can be checked against PayPal.**

Built for the PayPal AI Hackathon 2026. **Sandbox demonstration with synthetic data. Not legal advice.**

---

## What and why

Separated parents share "extraordinary" child expenses (orthodontics, camps, school trips) under agreements full of conditions: who pays what share, which costs need written agreement first, how fast to ask, how fast to pay. Every request turns into an argument about what the agreement says, and payments made by cash or app leave a shaky record.

Between does three things, in this order:

1. **An AI reads the agreement once.** It proposes rules. Each rule quotes its clause **word for word**, with page and section. Plain code then checks every quote against the document, and every number against its quote. Unclear or contradictory clauses become **questions for both parents, never guesses**.
2. **Both parents approve the exact rule set.** Questions are answered privately. When both pick the same answer, it becomes an *operational resolution*: "Your working arrangement in Between. It does not change your legal agreement." Nothing is used until both have approved that exact version.
3. **Plain code decides every expense and cites the clause.** No AI is involved in deciding. The parent who owes confirms, then pays through a **PayPal sandbox checkout** directly to the other parent's own PayPal account. Between counts the payment as paid **only after reading it back from PayPal**, and adds it to a tamper-evident record either parent can re-check.

## 60-second tour

1. Open the app and click **Try a demo family**. You get a synthetic family with a sample agreement (`samples/agreements/plan1_rivera_okafor.txt`) and 11 proposed rules.
2. **Rules.** Each rule shows its quote, page and section. Click **I approve these 11 rules**, then **Switch to Father** (a demo shortcut) and approve again.
3. **New expense.** Choose medical, attach `samples/receipts/ortho_420.png`, and confirm $420.00. The decision: **$252.00, Father owes Mother, due in 14 days**, citing §6.1 (p. 2) and §7.2 (p. 3).
4. **Switch to Father → Pay $252.00 with PayPal.** Confirm, approve in the PayPal sandbox as the Father's sandbox account (see *Judge sandbox accounts*), and come back to **Verified with PayPal**: paid $252.00, PayPal fee $9.28, received $242.72 (fee and received amount as reported by PayPal).
5. **Record.** Every step has an actor and a chain hash. **Check every payment with PayPal now** re-reads each capture from PayPal.

## Sandbox demonstration: what the PayPal flow is, and what it isn't

- **What it is.** A PayPal **Orders v2 checkout** (`intent=CAPTURE`). Between's server creates it with `purchase_units[0].payee.email_address` set to the receiving parent's account. The paying parent approves it on PayPal; Between captures it, then reads it back with `GET /v2/payments/captures/{id}`. In the sandbox, both parents are **personal** sandbox accounts.
- **What it isn't.** It is **not a Friends & Family transfer**. PayPal treats it as a commercial checkout: the receiving parent pays PayPal's fee, and the payment is eligible for PayPal seller protection.
- **Fees.** Before payment, Between shows the fee as an **estimate** (3.49% + $0.49, which is what the sandbox charged). After payment it shows PayPal's actual breakdown, labelled "from PayPal".
- **Open question.** Whether this checkout flow suits real-world parent-to-parent reimbursements under PayPal's terms is **unresolved**. It must be answered before any real launch.
- **What Between never does** (each was proven in a feasibility spike):
  - **Holds:** Between can't void a hold placed on a parent's account (`403`).
  - **Refunds:** Between can't refund a capture paid to a parent's account (`403`). Corrections are a payment back the other way, or the receiving parent refunds in PayPal and Between detects it.
  - **Payouts:** a payout is business-originated money, not a parent-to-parent payment.

## Not legal advice

Between coordinates expenses. It doesn't interpret the law. Approving rules or resolutions in Between doesn't change the legal agreement. Every agreement and receipt in this repository is **synthetic**.

## Architecture

```
browser (each parent) ── single-use invite → session cookie (HttpOnly, SameSite=Lax, CSRF on every form)
        │
FastAPI + Jinja2 (between/web)
  ├─ extraction.py   claude-sonnet-5-5 → proposed rules (structured output, no tools); claude-haiku-5-5 → receipt total
  ├─ validate.py     quote on page + right section + numbers in quote + percentages bound to the right parent
  ├─ ruleset.py      versions, both approvals, private answers, operational resolutions
  ├─ engine.py       pure decision: consent, deadlines, caps, splits in whole cents, citations
  ├─ payments.py     PayPal REST, sandbox only: create order (payee = parent), capture, GET order/capture, verify webhook
  ├─ reconcile.py    PayPal's capture → money status; verification separate; can downgrade on refund
  └─ record.py       hash-chained events, each with its actor
SQLAlchemy Core: SQLite locally, Postgres on Render
```

**The model never sets an amount, never authorizes a payment, and never changes an approved rule.**
- Rule numbers must appear in their quoted clause.
- Expense amounts come from the paying parent, who confirms what the AI read.
- Any change to the rules creates a new version that both parents must approve.

## Safety

| Control | How |
|---|---|
| Both parents approve the exact rules | The engine refuses unless both approvals match the rule set's sha256 |
| Fail closed | Contradictions, undefined words ("reasonable", "promptly") and disagreements go to both parents and are never decided |
| Private answers | The other parent's answer is never sent to you, not even hidden in the HTML, until both have answered |
| Explicit payer confirmation | Starting a checkout needs the payer's own session, a confirmation tick, and the current decision hash |
| Paid means verified | Paid only when PayPal's `GET capture` matches amount, payee and `custom_id`. Webhooks are verified, then only trigger that GET |
| No duplicate charges | Database-unique live payment per expense; deterministic `PayPal-Request-Id`s; webhook events deduplicated |
| Payer approved on PayPal but closed the tab | The verified `CHECKOUT.ORDER.APPROVED` webhook, or "check with PayPal", completes the capture with the same idempotent request id |
| Invites | Single use; expire after 72 h; re-issuing revokes the old link (refused once the other parent has joined) |
| Record | Every event has an actor and is chained to the previous one by sha256; edits and deletions are detected |
| No documents in logs | Logs hold ids, hashes and error codes only (canary test). Receipts are read in memory and never stored; only their hash |
| Hosted demo is synthetic only | Agreements must contain `SYNTHETIC DOCUMENT FOR SOFTWARE TESTING`; PayPal emails must be sandbox addresses; uploads ≤ 2 MB |

## What the feasibility spike proved (real sandbox calls)

- Personal → personal checkout: $252.00 captured, payee = the other parent's personal account; fee $9.28 charged to the payee.
- `GET capture` returns status, amount, payee and `custom_id` for a capture paid to a third party.
- Repeating a request ID returns the same capture; a new ID returns `ORDER_ALREADY_CAPTURED`.
- Webhooks for those captures reach the app; genuine signatures verify `SUCCESS` and tampered bodies `FAILURE`.
- Refunds and voids by the app on a parent's account: `403 PERMISSION_DENIED`. That's why the design has no holds and no refunds.

The same flow was then run through the app itself: $252.00 verified (capture `85D18309JT338721M`), and `scripts/verify.py` printed `completed verified … CHAIN OK`. See `docs/STATUS.md`.

## Run it locally

```bash
uv sync
cp .env.example .env      # fill in the sandbox values below
set -a; . ./.env; set +a
uv run uvicorn between.web.app:app --reload
# open http://127.0.0.1:8000 and click "Try a demo family"
```

| Variable | What |
|---|---|
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | A **sandbox** REST app from developer.paypal.com (Apps & Credentials, Sandbox) |
| `DEMO_PARENT_A_EMAIL`, `DEMO_PARENT_B_EMAIL` | Two US **personal** sandbox accounts (Testing Tools → Sandbox Accounts) |
| `PAYPAL_WEBHOOK_ID` | Optional locally: register `<public URL>/webhooks/paypal` (e.g. via a tunnel) for `CHECKOUT.ORDER.APPROVED` and `PAYMENT.CAPTURE.*` |
| `ANTHROPIC_API_KEY` | Optional. Without it, agreement reading says "AI unavailable" and you type the receipt amount; demo families ship with pre-extracted rules |
| `DATABASE_URL` | Defaults to `sqlite:///between.db`; Postgres URLs work too |
| `BETWEEN_BASE_URL` | Where PayPal sends the payer back (e.g. `http://127.0.0.1:8000`) |
| `BETWEEN_DEMO_MODE` | `1` = synthetic-only controls and the demo shortcuts |
| `BETWEEN_SECURE_COOKIES` | `1` behind HTTPS |

## Judge sandbox accounts

The hosted demo's two parents are dedicated **PayPal sandbox** personal accounts. Their sandbox logins are listed in the Devpost submission's testing instructions. They're test accounts in PayPal's sandbox and hold no real money.

## Tests

```bash
uv run pytest -q                                          # 151 tests: validator, engine, approvals, access, PayPal client and reconciliation (on recorded sandbox responses), routes, security headers, logging canary
uv run python scripts/eval_extraction.py --runs 2         # AI extraction gate (needs ANTHROPIC_API_KEY): 3 agreements + 1 planted-instruction agreement
uv run python scripts/e2e_sandbox.py --base-url http://127.0.0.1:8000   # golden path with a real sandbox approval
uv run python scripts/verify.py --family <id>             # independent check of every payment against PayPal + the record chain
```

## Hosting (Render)

`render.yaml` defines one web service and a Render Postgres database. **Free Render Postgres expires 30 days after creation** (`render.com/docs/free`). Before that date, either upgrade the database or point `DATABASE_URL` at a new one. On start, the app re-creates the base demo family if it's missing; it never overwrites or deletes data.

## What came from Kitty

Between reuses a few small, tested pieces from the author's earlier project Kitty (a group-trip settlement app): the single-use-invite → session pattern (`access.py`), the hash-chain idea (`record.py`), the integer-money style, the CSS tokens, and the Anek Latin font (SIL OFL, `between/web/static/fonts/OFL.txt`). Between itself (rule extraction, validation, two-parent approval, the decision engine, PayPal integration and reconciliation) was built during the hackathon submission period.

## Built with

- Anthropic Claude: `claude-sonnet-5-5` reads agreements (structured outputs, server-side refusal fallback); `claude-haiku-5-5` reads receipt totals.
- PayPal: Orders v2 (create, capture, get), Payments v2 (get capture), Webhooks (verify-webhook-signature), sandbox only.
- FastAPI, SQLAlchemy, Jinja2, pypdf, httpx. Hosting on Render.

## Licence

MIT. See `LICENSE`.
