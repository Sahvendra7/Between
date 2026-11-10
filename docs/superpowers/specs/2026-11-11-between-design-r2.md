# Between: design spec, revision 2

Written Wed 11 Nov 2026, 03:20 IST.

- **Supersedes** `2026-11-11-between-design.md` (r1). Everything in r1 not changed here still stands; this file is self-contained so the plan needs only this one.
- **Status:** r1 approved in principle by the owner. This revision applies the owner's review.
- **Evidence:**
  - `../../../../spike/SPIKE_REPORT.md` (real sandbox and model results)
  - `../../../../ROUND_2_IDEATION_AND_FINAL_SELECTION.md` (why Between)

**What changed from r1:**

| # | Area | Change |
|---|---|---|
| 1 | PayPal | Wording: a sandbox **checkout** between personal accounts, not Friends & Family. Fees are **estimates** until PayPal's breakdown arrives. Real-world suitability is an open terms question |
| 2 | Deployment | Render **Postgres** for the hosted demo, SQLite locally. Seeding is idempotent and non-destructive. Receipt images are not kept |
| 3 | Anthropic | No `temperature`/`top_p`/`top_k`. Structured outputs. The validators are unchanged |
| 4 | Rules | Two kinds: **agreement rules** and **operational resolutions**. Resolutions don't amend the legal agreement. Fail-closed is kept |
| 5 | Payments | Money state and verification state are separate. Adds pending / partially_refunded / refunded / reversed and verification_unavailable. Tracks gross, fee, net and last-verified time. Re-verification can change a verified payment |
| 6 | Scope | The five-step golden path is P0. AI decline drafting is cut. Consent is simplified. The read-only Bryntum Community calendar is first in P1 |
| 7 | Security | Private-answer isolation, cookie flags + CSRF, invite expiry and rotation, synthetic-only demo controls, actor attribution, DB-enforced idempotency |

---

## 1. What we're building

Between helps separated parents share child expenses without arguing about what their agreement says.
1. A parent uploads the co-parenting agreement.
2. An AI proposes expense rules. Each rule quotes its exact clause, page and section. Unclear or contradictory clauses become **questions**, never guesses.
3. **Both** parents approve the exact rule set.
4. A parent submits an expense. Plain code (no AI) decides who owes what, by when, and why, citing the clauses.
5. The owing parent confirms, and a **PayPal sandbox checkout** moves the share from the payer's personal sandbox account to the other parent's personal sandbox account.
6. Between confirms the payment with PayPal and adds it to a tamper-evident record.

**Between is expense coordination. It is not legal advice and it doesn't enforce anything.** Approving rules or resolutions in Between doesn't change the legal agreement.

## 2. Understanding (unchanged from r1, restated)

- **Goal:** a real, working entry for the PayPal AI Hackathon 2026. The targets are Most Impactful + Best Use of Bryntum.
- **Constraints:**
  - Deadline **Fri 13 Nov, 01:30 IST**; internal submit target **Thu 12 Nov, 18:00 IST**; feature freeze **Thu 12:00 IST**.
  - PayPal sandbox only; synthetic data only.
  - A public repo with an MIT license.
  - A hosted demo plus run steps.
  - A YouTube video under 3:00.
  - Kitty is not modified.
- **Success:** in under 3 minutes a judge sees:
  1. an agreement become cited rules;
  2. both parents approve them;
  3. an expense decided with citations;
  4. a real sandbox payment from one parent's account to the other's;
  5. an independent check against PayPal.

## 3. PayPal: what the flow is, and what it is not

**What it is [Fact, spike P2/P3/P7/P8]:**
- A **PayPal Orders v2 checkout** (`intent=CAPTURE`).
- Between's server creates it with `purchase_units[0].payee.email_address` set to the receiving parent's account.
- The paying parent approves it on PayPal; Between captures it; Between reads it back with `GET /v2/payments/captures/{id}`.
- In the sandbox, both parents are **personal** sandbox accounts, and the payment went from one to the other.

**What it is not:**
- **Not a Friends & Family personal transfer.** F&F is a feature of PayPal's own apps. This REST checkout flow doesn't offer it **[Inference]**.
- PayPal treats the payment as a commercial checkout. The receiving account is charged a fee, and the capture is marked `seller_protection: ELIGIBLE`.
- **Open question:** whether this checkout flow suits real-world parent-to-parent reimbursements under PayPal's terms. Unresolved. It must be answered before any real launch. The README and the video say "sandbox demonstration".

**Fees:**
- **Before** payment, the UI shows an **estimate**, labelled as one: "PayPal will charge the receiving parent about $9.28 (estimate)". The estimate is `round(gross × 3.49%) + $0.49`, matching what the sandbox charged in the spike.
- **After** capture, the UI shows PayPal's actual `seller_receivable_breakdown` (gross, fee, net), labelled "from PayPal".

**Consequences carried from the spike:**
- No holds (Between can't void them on a parent's account).
- No refunds by Between (403). Corrections are reverse payments.
- No Payouts (business-originated; also not permitted on this sandbox business account).
- `GET capture` is the source of truth. Webhooks are verified hints.

## 4. Scope

**P0, the golden path, built and tested first in this order:**
1. **Agreement → rules.** Upload a synthetic agreement. The AI extracts rules (structured output), the deterministic validator grounds them, and the review screen shows each rule with its quote.
2. **Both parents approve.** Each approves the exact version (hash). Questions are answered privately; a matching pair of answers becomes an operational resolution (§6), which leads to a new version to approve.
3. **Expense decided.** Submit an expense: the AI reads the receipt total in memory, then the payer confirms the amount. The engine decides, with citations. Consent is the simplified version (§6.3).
4. **Payment.** The payer confirms, a PayPal sandbox checkout runs to the other parent's account, and Between captures.
5. **Verification and record.** `GET capture` reconciliation; the hash-chained record with actor attribution; `verify` (script and page); export.

**Also P0, because the path needs them:**
- Family creation and invite links.
- Sessions, CSRF and the demo controls.
- Webhook endpoint (verified hint).
- Idempotent seed.
- Render deploy with Postgres.
- README, LICENSE, sandbox test accounts.

**P1, in this order; each starts only if its time budget fits before the freeze:**
1. **Read-only Bryntum Calendar (Community, MIT)** of parenting time. It's extracted from the same agreement (AI → typed schedule → deterministic expansion), with expenses shown on their dates.
2. **Corrections** by reverse payment.
3. **Fee-sharing resolution** ("payer covers the PayPal fee"), as an operational resolution both approve.
4. **Side-by-side stage page** for the video.

**P2, not built:**
- AI-drafted decline or consent messages (cut from r1's P0).
- Multiple children; recurring support.
- Non-USD; scanned-PDF OCR.
- Notifications; mediator accounts.

## 5. Architecture

One Python service: FastAPI, Jinja2 templates, a little vanilla JS. **SQLAlchemy Core** with one schema for both databases: **SQLite locally, Render Postgres hosted** (`DATABASE_URL`). No frontend build; Bryntum's ES modules are vendored as static files (P1).

**Modules:**

| Module | Responsibility |
|---|---|
| `config.py` | Settings from env |
| `db.py` | Tables, indexes, engine |
| `money.py` | Cents parsing and formatting, split, fee estimate |
| `agreement.py` | Pages, labels, locate, PDF→text |
| `validate.py` | Grounding (from the spike) |
| `engine.py` | Pure decision (from the spike + resolutions + simplified consent) |
| `ruleset.py` | Versions, approvals, private answers, resolutions |
| `record.py` | Hash-chained events with actor |
| `access.py` | Invites, sessions, CSRF |
| `extraction.py` | Anthropic calls |
| `payments.py` | PayPal REST |
| `reconcile.py` | PayPal capture → payment state |
| `demo.py` | Idempotent seed and synthetic controls |
| `web/` | Routes and templates |
| `scripts/verify.py`, `scripts/eval_extraction.py`, `scripts/e2e_sandbox.py` | Command-line checks |

**Kitty code copied, unchanged in Kitty:**
- `access.py` (invite → cookie)
- `pot.py` chain functions (widened to 64-hex)
- money formatting pattern
- `kitty.css` tokens and the Anek Latin font (OFL), without the cat

## 6. Rules: two kinds, one fail-closed engine

### 6.1 Agreement rules
- Extracted by the AI and grounded by the validator: exact quote, page, section, numbers in the quote, percentages bound to the right parent.
- `origin: "agreement"`, with `source: {quote, page, section}`.
- Contradictions and undefined qualifiers become **questions**, never rules.

### 6.2 Operational resolutions
- **What one is:** when a question exists (an ambiguity or a contradiction), each parent answers **privately** by choosing one option.
- **What happens next:**
  - If both choose the same option, Between creates an **operational resolution**: `origin: "resolution"`, `source: {question_id, answered_by: ["A", "B"], answered_at}`. It then creates a new rule-set version that both must approve.
  - If they differ, or either hasn't answered, the question stays open, and every expense it touches returns **`needs_parents`** (fail closed).
- **Shown everywhere as** "Your working arrangement in Between. **It does not change your legal agreement.**" It is visually distinct from agreement rules, and its citation chip reads "Resolution R3", not a clause number.
- **Limits:**
  - A resolution may only fill a question. It can't override or delete an agreement rule.
  - The validator skips the quote checks for resolutions, but still checks kind, category, params, shares totalling 100, and that the question exists.
- **Options** come from deterministic templates per question type:
  - **Contradiction:** "Use clause X" / "Use clause Y" / "Decide each expense together".
  - **Undefined qualifier:** "Every cost in this category counts" / "Decide each expense together".
  - **Missing number** ("promptly"): "N days", where both parents enter N and must match / "No deadline in Between".

  The AI doesn't write options. "Decide each expense together" creates no rule, so the question stays and the category stays `needs_parents`.

### 6.3 Consent (simplified)
- **One mechanism.** A parent asks in advance: `{category, max_minor, note}`. The other parent taps **Agree**, which records `given_by` and `given_on`.
- **The engine treats a consent as valid for an expense when:**
  - `category` matches;
  - `amount ≤ max_minor`;
  - `given_by` is the non-paying parent;
  - `given_on ≤ incurred_on`;
  - the consent isn't already used up.
- **A consent covers one expense.** It's marked used when the expense is decided.
- This covers r1's per-expense and "standing" consents with one rule.
- The emergency exception is unchanged: if the agreement has one, the payer can tick "emergency", and the decision notes the notify-within-N-hours obligation.

### 6.4 Engine behaviour (unchanged from the spike unless noted)
The engine is pure and makes no network calls. It refuses (`refused`) unless both parents' approvals match the current version hash. Then:
1. not shared → `rejected`
2. open blocking question → `needs_parents`
3. no split rule → `needs_parents`
4. receipt required and missing → `rejected`
5. requested too late → `rejected`
6. over the consent threshold without a valid consent → `needs_consent`
7. `covers_first`
8. split (largest-remainder cents)
9. annual cap
10. due date

Every result cites agreement sections or resolution ids.

## 7. AI design

**Calls:**
- **Rule extraction and P1 schedule extraction:** `claude-sonnet-5-5`.
- **Receipt total:** `claude-haiku-5-5`.
- **SDK:** the official Anthropic Python SDK, `client.messages.parse(..., output_format=<Pydantic model>)`. Structured output means the response is schema-valid JSON; the deterministic validators then decide what's grounded.
- **No `temperature`, `top_p` or `top_k`** on any request (they're rejected on these models).
- **Effort and thinking:** model defaults (no thinking configuration sent).
- **`max_tokens`:** 16000 for extraction, 1024 for receipts.

**Refusals and errors fail closed:**
- `stop_reason == "refusal"`, an API error, a timeout or a missing key all raise `AIUnavailable`, and the UI says "The AI couldn't read this; nothing was changed".
- The seeded demo family ships with an already-approved rule set, so the payment path works with no model.
- Server-side refusal fallback (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) is enabled on the Sonnet call **only if** the installed SDK accepts it in the extraction task's live check. Otherwise refusal fails closed as above.

**Inputs are data:**
- The model has no tools.
- Agreement and receipt text can't reach PayPal or the DB except through the validator and human confirmation.
- A planted-instruction agreement is part of the extraction eval.

**Receipts:**
- The image bytes are read in memory, sent to the model, and **discarded**.
- Between stores only `receipt_sha256` (duplicate detection) and the payer-confirmed fields.
- No receipt file is written to disk or the DB.

**Logging:** ids, hashes, timings and error codes only. No document text, quotes, prompts, model output or receipt content. A canary test enforces this.

## 8. Payments: state and reconciliation

**Two separate fields on `payment`:**

| Field | Values | Set by |
|---|---|---|
| `status` (money state, PayPal's view) | `created` → `approved` → `pending` / `completed` → `partially_refunded` / `refunded` / `reversed`; or `declined` / `failed` / `cancelled` | Only by reconciling a `GET capture` (or `GET order` before capture) |
| `verification` | `unverified`, `verified`, `verification_unavailable` | `verify_payment()` |

**Other columns:** `gross_minor`, `fee_minor`, `net_minor` (from PayPal's breakdown; NULL until known), `fee_estimate_minor`, `paypal_status` (raw), `last_verified_at`, `last_error`.

**Rules:**
- **When a payment counts as paid:** only when `status ∈ {completed, partially_refunded}` and `verification = verified`. A refund or reversal reduces what counts: `net counted = gross − refunded`. If that's not available, the expense reopens as "payment refunded".
- **Re-verification:** every `verify` run (page button, script, webhook hint) re-reads PayPal and **may change** an already verified payment, e.g. `completed` → `refunded` when the receiving parent refunds in PayPal. Each change appends a `payment.status_changed` event with old and new values.
- **PayPal unreachable:** `verification = verification_unavailable`, `status` unchanged (never downgraded on an error), `last_error` set, retried on the next verify.
- **Capture status mapping (`GET /v2/payments/captures/{id}`):**
  - `COMPLETED` → `completed`
  - `PENDING` → `pending`
  - `PARTIALLY_REFUNDED` → `partially_refunded`
  - `REFUNDED` → `refunded`
  - `DECLINED` → `declined`
  - `FAILED` → `failed`
  - Anything else → `status` unchanged, plus `last_error = "unknown_capture_status:<value>"`.
- **Reversals [mapping unverified in sandbox]:** a verified `PAYMENT.CAPTURE.REVERSED` webhook sets `status = reversed` only when the follow-up `GET capture` no longer reads `COMPLETED`. Otherwise Between records `reversal_reported_unconfirmed` and keeps the status.

**Idempotency (database-enforced):**
- `payment.request_id` is UNIQUE, and the derived PayPal request ids are deterministic (`pay_<id>_create`, `pay_<id>_capture`).
- A partial UNIQUE index on `payment(expense_id, kind)` where `status NOT IN ('failed', 'declined', 'cancelled')` allows one live payment per expense and kind.
- `webhook_event.id` is a PRIMARY KEY (dedupe).
- `expense(family_id, receipt_sha256)` is UNIQUE.
- `consent.used_by_expense_id` is UNIQUE.

## 9. Security

| Control | Specification |
|---|---|
| **Private answers** | Stored per `(ruleset_id, question_id, role)`. Routes return the other parent's answer **only after both have answered**. The server never sends it earlier, not even hidden in HTML. Tested |
| **Sessions** | A random 32-byte session id in a cookie, stored hashed. `HttpOnly`, `SameSite=Lax`, `Secure` when `BETWEEN_SECURE_COOKIES=1` (hosted), `Path=/`, 14-day expiry |
| **CSRF** | Synchronizer token per session, in every form as a hidden field and required on every POST except `/webhooks/paypal` (authenticated by PayPal signature instead) |
| **Invites** | Single use, **expire after 72 h**. Creating a new invite for a role **rotates**: the old token and any session it created are revoked. Tokens are stored hashed |
| **Role isolation** | Every family route checks that the session belongs to that family. A parent can approve, answer or pay only as their own role. The payer is always the session's role |
| **Explicit payer confirmation** | Creating an order requires a POST from the payer's session carrying `confirm=yes` and the current `decision_hash` |
| **Actor attribution** | Every event stores `actor = {kind: parent|system|paypal, role, session_ref}` (`session_ref` = the first 8 hex characters of the session hash). Events are hash-chained (64-hex) |
| **Synthetic-only hosted demo** (`BETWEEN_DEMO_MODE=1`) | (a) A banner on every page. (b) Agreements must contain the line `SYNTHETIC DOCUMENT FOR SOFTWARE TESTING`, or they're refused. (c) PayPal emails must end in `@personal.example.com` or `@business.example.com` (sandbox addresses). (d) Receipts ≤ 2 MB, PNG/JPEG/PDF, never stored. (e) Agreement text ≤ 60,000 characters. (f) No real-PayPal (live) code path exists at all |
| **Headers** | `Content-Security-Policy` (self + PayPal sandbox redirect target), `X-Frame-Options: DENY`, `Referrer-Policy: same-origin` |

## 10. Data model (SQLAlchemy Core; identical on SQLite and Postgres)

| Table | Columns (key ones) | Constraints |
|---|---|---|
| `family` | `id`, `created_at`, `currency`, `demo_key` | `demo_key` UNIQUE NULL (idempotent seed) |
| `parent` | `family_id`, `role`, `label`, `display_name`, `paypal_email` | PK (`family_id`, `role`) |
| `invite` | `token_hash` PK, `family_id`, `role`, `expires_at`, `used_at`, `revoked_at` | |
| `session` | `id_hash` PK, `family_id`, `role`, `csrf`, `created_at`, `expires_at`, `revoked_at` | |
| `agreement` | `id`, `family_id`, `sha256`, `text`, `uploaded_by`, `uploaded_at` | Text stored unencrypted for the synthetic demo (README says a real deployment encrypts it) |
| `ruleset` | `id`, `family_id`, `agreement_id`, `version`, `json`, `hash`, `created_at` | UNIQUE (`family_id`, `version`) |
| `approval` | `ruleset_id`, `role`, `hash`, `at` | PK (`ruleset_id`, `role`) |
| `answer` | `ruleset_id`, `question_id`, `role`, `choice`, `value`, `at` | PK (`ruleset_id`, `question_id`, `role`) |
| `expense` | `id`, `family_id`, `paid_by`, `category`, `amount_minor`, `incurred_on`, `requested_on`, `receipt_sha256`, `emergency`, `status` | UNIQUE (`family_id`, `receipt_sha256`) |
| `consent` | `id`, `family_id`, `requested_by`, `category`, `max_minor`, `note`, `given_by`, `given_on`, `used_by_expense_id` | UNIQUE (`used_by_expense_id`) |
| `decision` | `expense_id` PK, `ruleset_hash`, `json`, `hash`, `at` | |
| `payment` | §8 columns + `id`, `expense_id`, `kind`, `payer_role`, `payee_role`, `amount_minor`, `order_id`, `capture_id`, `request_id` | §8 indexes |
| `webhook_event` | `id` PK, `type`, `resource_id`, `verified`, `received_at` | |
| `event` | `family_id`, `seq`, `type`, `body_json`, `actor_json`, `prev`, `hash`, `at` | PK (`family_id`, `seq`) |

## 11. Deployment

**Local:** SQLite file `between.db`, `uv run uvicorn between.web.app:app`.

**Hosted on Render (`render.yaml`):**
- One free web service plus **Render Postgres**.
- `DATABASE_URL` comes from the database.
- Migrations: `metadata.create_all` on start (new tables only, never drops).

**Seeding (`demo.seed()`), idempotent and non-destructive:**
- Runs on every start.
- Creates the base demo family (`demo_key = "demo-1"`) only if it doesn't exist.
- Never updates or deletes existing rows.
- A "Try a demo family" button creates a **new** family per visitor from the samples. Visitors never share or overwrite each other's data.

**Postgres expiry, for the owner to decide:**
- Render's **free** Postgres expires **30 days after creation** (`render.com/docs/free`). Created 11 Nov, it expires 11 Dec, **before judging ends 15 Dec**. There's a 14-day grace period to upgrade before deletion.
- **Options:**
  - (a) Upgrade the database to a paid plan before 11 Dec (the owner's spend).
  - (b) Before 11 Dec, create a new free database, point `DATABASE_URL` at it, and redeploy. Seeding restores the demo family; visitor families are lost.
  - (c) Accept that the hosted demo may be down 11–15 Dec; local run steps still work.
- **Recommendation:** (a) if the owner accepts the cost, else (b), with a calendar reminder.

**Environment variables:** `DATABASE_URL`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`, `ANTHROPIC_API_KEY` (optional), `BETWEEN_SECRET`, `BETWEEN_BASE_URL`, `BETWEEN_DEMO_MODE`, `BETWEEN_SECURE_COOKIES`.

**Webhook:** registered against `BETWEEN_BASE_URL/webhooks/paypal`.

**Judge access:** two dedicated demo sandbox personal accounts, with their sandbox logins in the README (test credentials, as the rules allow).

## 12. Testing

- **Unit (pytest, no network):**
  - the spike's 26 tests, ported;
  - money parsing;
  - resolutions and fail-closed;
  - consent;
  - ruleset versioning and private answers;
  - access (expiry, rotation, CSRF, cookie flags);
  - record chain and actor;
  - payments against **recorded spike responses**;
  - the reconcile state machine (every mapping, re-verification downgrade, `verification_unavailable`);
  - idempotency constraints (DB raises on duplicates);
  - routes (isolation, confirm required);
  - logging canary;
  - demo controls.
- **Postgres:** the same DB tests run against Postgres when `TEST_DATABASE_URL` is set.
- **Extraction eval:** 3 synthetic agreements + 1 injection agreement. Gate: all key rules, all expected questions, injection refused, 0 wrong amounts in the scenario comparison.
- **Sandbox end-to-end:** the golden path through HTTP routes, with the PayPal approval done in a browser, then `verify`.
- **Browser check:** 390 px and 1280 px, no console errors.

## 13. Risks

| Risk | Mitigation |
|---|---|
| Judges read it as "Splitwise for divorce" | Open the video on citations and two-parent approval |
| PayPal terms for real reimbursements via checkout | Open question; sandbox-only wording |
| Payer dispute exposure (`seller_protection` eligible) | Stated; the record is evidence |
| Free Postgres expiry before judging ends | §11 owner decision |
| Bryntum Community via vendored ES modules fails to load | P1 time-boxed; the calendar is cut, not faked |
| Untested on real, long, scanned agreements | Scoped to text agreements; validator + both approvals |
| Render cold start (~1 min) | README note; record the video on a warm instance |

## 14. Open questions for the owner

1. The repo: `~/Desktop/PayPal/between` → `github.com/Sahvendra7/between` (public at submission).
2. Is an Anthropic API key available for the hosted demo?
3. The Postgres expiry choice (§11).
4. Commits during execution, local only; pushing only with your go-ahead.
5. The video only with your go-ahead.
