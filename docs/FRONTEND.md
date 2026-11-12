# Between frontend (Next.js on Vercel)

The new frontend lives in `frontend/`. It is a Next.js 16 App Router app deployed on Vercel. Every business decision, payment and record still lives in the FastAPI backend on Render. The Render site keeps its own HTML UI and works as a fallback.

| | URL |
|---|---|
| Vercel production | https://between-app-iota.vercel.app |
| Vercel preview (protected by Vercel login) | https://between-85yfz1gz7-sahvendra7s-projects.vercel.app |
| Render (backend, and fallback UI) | https://between-vjte.onrender.com |

## Architecture

```
Browser ──► Vercel (Next.js)                              ──► Render (FastAPI)
            · app/[...path]/page.tsx: GET the same path ─────► render() returns {template, ctx} JSON
              and render the matching React screen               (x-between-json: 1)
            · app/actions.tsx: every form → POST ────────────► same routes, same CSRF tokens;
              303 → redirect(), page → screen in place           Set-Cookie copied to the Vercel origin
            · rewrites: /static/*, calendar.json, money.json,
              /money/ai, /money/preview, /money/expense/* ───► straight through, same origin
PayPal webhooks ─────────────────────────────────────────────► Render /webhooks/paypal (unchanged)
```

- **There is one URL space.** Each frontend URL is the backend's own URL (`/f/{fid}/rules`, `/pay/return?p=…`). The catch-all page fetches that path from FastAPI in JSON mode and renders the screen for the template it names. Routing, permissions and redirects stay entirely in FastAPI.
- **Sessions stay first-party.** The browser only ever talks to the Vercel origin. The server action copies FastAPI's `between_session` cookie onto the Vercel origin (`HttpOnly`, `SameSite=Lax`, `Secure` in production). The page and action code forward only that cookie to Render, server to server. There are no cross-site cookies and no CORS.
- **CSRF protection has two layers.** FastAPI's per-session token still travels in every form. Next.js server actions also reject cross-origin posts.
- **PayPal flow:**
  - Order creation, approval redirect, capture, read-back, idempotency and webhooks are unchanged.
  - The only change: the return and cancel URLs (and invite links) use the origin the proxy reports in `x-between-origin`, and only when that origin is listed in `BETWEEN_FRONTEND_ORIGINS`. Otherwise they fall back to `BETWEEN_BASE_URL`, so an unknown host can't steer a return URL.
  - The webhook stays registered at Render.
- **Bryntum and AG Studio** reuse the existing `static/calendar.js` and `static/money.js` unchanged.
  - They load only on the Calendar and Money & Time pages.
  - AG Studio still comes from jsDelivr, pinned with SRI, and is never vendored.

### Backend changes (smallest safe change)

- `between/web/deps.py`:
  - `render()` returns the template context as JSON when asked. Rule wording comes from `present.describe_rule`, and a `viewer` block names the signed-in parent.
  - `public_base()` picks an allowlisted frontend origin.
- `between/config.py`: `BETWEEN_FRONTEND_ORIGINS`, a comma-separated list of exact origins.
- `between/web/app.py`: errors use `render()` too.
- `routes_family.py` and `routes_pay.py`: invite and PayPal return/cancel URLs use `public_base()`.
- Tests: `tests/test_web_json.py` (4 tests). The suite is now 220 passing.

## Security review

- **Secrets:** PayPal, Gemini, database and signing secrets stay on Render. Vercel has one server-only variable, `BETWEEN_BACKEND_URL`. Nothing uses `NEXT_PUBLIC_`.
- **SSRF:** `lib/backend.ts` refuses any path that would resolve outside the backend origin.
- **CSP** is set per request in `proxy.ts`:
  - `script-src 'self' 'nonce-…' 'strict-dynamic'`; scripts never run inline without the nonce.
  - `style-src 'self' 'unsafe-inline'`, because React style props, the CSS story and AG Studio set inline styles. The old Render CSP allowed this only on the Money page.
  - `form-action 'self' https://www.sandbox.paypal.com`, `frame-ancestors 'none'`, `object-src 'none'`.
- **Headers:** `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, `X-Content-Type-Options: nosniff`.
- **JSON mode** returns the same data the HTML page already showed to the same session. Without a session it returns the same 403 as before.
- **What the frontend never decides:** amounts, approvals, payment authorisation, verification and the record chain. The UI only formats what the backend sends. The two pieces of arithmetic in TS are display-only: the cap bar's width, and counting window states.

## Design system

- **Type:**
  - Anek Latin (variable width) is Between's voice; headlines use the narrow width.
  - Source Serif 4 is used **only** for words quoted from the agreement, so a serif always means "your document says this".
- **Colour:**
  - Tokens are defined once in `app/globals.css`, for light and dark.
  - Teal is Parent A, ochre is Parent B, indigo is Between's actions.
  - Status: green means verified, amber means waiting on a person, rose means not shared.
  - Slate ink sits on porcelain paper.
- **Components:**
  - `components/ui.tsx`: PageHead, Pill, Who, Clause, Section and Empty.
  - `components/backend-form.tsx`: BackendForm and Submit, with pending states.
  - `components/shell.tsx`: sidebar on desktop; top bar plus bottom tabs on mobile; "Signed in as" is always visible.
  - Screens are in `components/screens/`. All screens are Server Components. The client components are the form, nav, copy/print, vendor mount and scroll story.

## Motion inventory

| Where | What | How |
|---|---|---|
| Landing hero (signature) | A highlighter sweeps clause 6.1, then the verified decision settles on top. Plays once, in about 1.8 s. | CSS keyframes |
| Landing "From a clause to a verified payment" | A sticky product story: Agreement → Approved rules → Decision → Verified with PayPal changes as each step reaches mid-screen. Has a step indicator and a progress line. On mobile, each step shows its own static visual. | IntersectionObserver, CSS crossfade, CSS scroll-driven timeline (progressive) |
| Route changes | A short crossfade. The expense row's title morphs into the expense page heading. | React `<ViewTransition>` (native View Transitions) |
| Payment result | The verified tick draws once. | SVG stroke animation |
| Buttons, choices, links | Press, hover, focus and pending spinners. | CSS transitions |

- There is no scroll hijacking, no Lenis and no GSAP; the app's scrolling is native.
- `prefers-reduced-motion` turns off every animation and transition and shows the final state.
- Motion (the library) was tried for the scroll story and removed: the same effect costs about 49 KB less with an IntersectionObserver and CSS.

## Results (12 Nov 2026)

- **Playwright, local dev:** 10/10 passed.
  - Chromium:
    - Landing.
    - Two parents in separate browser contexts, through invite and join, with single-use links and a stranger blocked.
    - The full demo journey: rules approved by both, private answers, receipt upload, decision with clause, highlighted source, explicit pay confirmation and hand-off to `sandbox.paypal.com`, record and export, Money & Time with Bryntum and AG Studio, and the calendar.
  - WebKit and Pixel 7 emulation: smoke tests.
- **axe-core:** 0 serious or critical violations on the landing, home, rules, agreement, new expense, record, calendar and money pages. AG Studio and Bryntum widgets are excluded from the scan as third-party code.
- **Screenshots:** 375, 768 and 1440 px, in light and dark, with motion and with reduced motion (`frontend/screens/`, not committed). There is no horizontal overflow at any width.
- **Lighthouse 13.6, mobile, local production build, landing:**
  - Performance 100, Accessibility 100, Best Practices 100, SEO 91.
  - LCP 0.9 s, CLS 0, TBT 30 ms.
- **Landing JS:** 184 KB gzipped, of which about 176 KB is the React 19 and Next.js runtime that every App Router page loads. That is an exception to the ~150 KB target, and it can't be met without leaving the App Router.
- **Hosted results** are in `docs/STATUS.md`.

## Run it locally

Run the backend:

```bash
BETWEEN_FRONTEND_ORIGINS=http://localhost:3000 uv run --env-file .env uvicorn between.web.app:app --port 8000
```

Then the frontend, from `frontend/`:

```bash
npm install
```

```bash
BETWEEN_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Run the tests against local dev:

```bash
npx playwright test
```

Run them against a deployment:

```bash
E2E_BASE_URL=https://between-app-iota.vercel.app npx playwright test
```

## Vercel

- **Project:** `between-app` (Hobby). Root directory `frontend/`. Deployed with the CLI (`vercel deploy`, then `vercel deploy --prod`); the project has no Git integration.
- **Environment:** `BETWEEN_BACKEND_URL=https://between-vjte.onrender.com` (Production, Preview, Development). It is read at build time for the rewrites and at run time by the proxy.
- **Render:** `BETWEEN_FRONTEND_ORIGINS` lists the production alias and the tested preview URL. Each new preview URL must be added there before testing invite links or PayPal returns on it.

## Known limitations

- Vercel promoted the project's first CLI deployment straight to production, before a separate preview existed. The preview was deployed and smoke-tested next (through `vercel curl`, since previews are behind Vercel login).
- A full sandbox capture → return → verify through the Next.js frontend passed on local dev (`tests/paypal-local.spec.ts`, capture 7JJ82421FH569103Y). On the hosted Vercel site, the automated tests stop at the hand-off to `sandbox.paypal.com`. A hosted approval needs a person (`tests/paypal-manual.spec.ts`, headed). The return URL there comes from the same allowlist, which the invite-link test proves on production.
- The theme follows the system (`prefers-color-scheme`). There is no manual toggle, which avoids an inline script before paint.
- The AG Studio trial watermark and licence banner show until `AG_STUDIO_LICENSE` is set. AG Studio's charts use a system font, because the next/font family name is hashed.
- shadcn/ui, Radix, GSAP and Lenis were not added: the app has no menus, dialogs or popovers, and the motion above needs none of them. The skills for them were not installed in this environment.
