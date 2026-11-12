import Link from "next/link";
import { ViewTransition } from "react";
import { Baby, BookOpen, Bus, Gift, GraduationCap, HeartPulse, Pencil, Plane, Shirt, Tent, Trophy, Utensils } from "lucide-react";
import type { Envelope } from "@/lib/types";
import { stamp, usd } from "@/lib/format";
import { BackendForm, Submit } from "../backend-form";
import { Clause, PageHead, Pill, Section, Who } from "../ui";

type P = { env: Envelope };
const ICONS: Record<string, typeof Baby> = {
  medical: HeartPulse, extracurricular: Trophy, education: GraduationCap, childcare: Baby, camp: Tent, travel_child: Bus,
  travel_parent: Plane, clothing: Shirt, gifts: Gift, food: Utensils, school_supplies: BookOpen,
};

export function ExpenseNew({ env }: P) {
  const { s, fid, categories = [], today, emergency_allowed } = env.ctx;
  const name = (c: string) => env.words.categories[c] ?? c;
  return (
    <>
      <PageHead title="New expense" lede="Tell Between what you paid. It reads the receipt's total, you confirm the amount, and your approved rules decide the rest." />
      <Section className="mb-6">
        <BackendForm to={`/f/${fid}/expenses/new`} csrf={s.csrf} className="grid gap-6">
          <fieldset className="m-0 border-0 p-0">
            <legend className="mb-3 font-semibold">What was it for?</legend>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {categories.map((c: string) => {
                const Icon = ICONS[c] ?? Pencil;
                return (
                  <label key={c} className="choice !items-center !py-3">
                    <input type="radio" name="category" value={c} required className="sr-only" />
                    <Icon size={18} aria-hidden className="flex-none text-ink-2" /><span className="leading-tight">{name(c)}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="field">Date you paid<input type="date" name="incurred_on" defaultValue={today} max={today} /></label>
            <label className="field">Receipt<input type="file" name="receipt" accept="image/png,image/jpeg,application/pdf" /><span className="help">PNG, JPEG or PDF, up to 2 MB. Read, then discarded: only its fingerprint is kept.</span></label>
          </div>
          {emergency_allowed ? <label className="choice w-fit"><input type="checkbox" name="emergency" /> This was an emergency</label> : null}
          <div className="flex flex-wrap items-center gap-4">
            <Submit pendingText="Reading the receipt…">Continue</Submit>
            <p className="hint m-0">You confirm the amount on the next step.</p>
          </div>
        </BackendForm>
      </Section>
      <Section title="Ask to agree in advance" hint="Some agreements need the other parent's written agreement before you spend over a limit.">
        <BackendForm to={`/f/${fid}/consents`} csrf={s.csrf} className="grid gap-4 sm:grid-cols-2">
          <label className="field">For<select name="category" required>{categories.map((c: string) => <option key={c} value={c}>{name(c)}</option>)}</select></label>
          <label className="field">Up to (USD)<input name="max" inputMode="decimal" required placeholder="300.00" /></label>
          <label className="field sm:col-span-2">Note for the other parent<input name="note" maxLength={500} placeholder="Summer soccer camp" /></label>
          <div className="sm:col-span-2"><Submit variant="quiet">Send request</Submit></div>
        </BackendForm>
      </Section>
    </>
  );
}

export function ExpenseConfirm({ env }: P) {
  const c = env.ctx;
  return (
    <>
      <PageHead title="Confirm the amount" lede="Only the amount you confirm counts. The AI's reading is a suggestion." />
      <section className="sheet mx-auto max-w-xl">
        <p className="m-0 text-[1.05rem]">
          {c.amount ? <>We read <strong>${c.amount}</strong>{c.merchant ? <> from {c.merchant}</> : null}. Is that what you paid?</> : "Enter the amount you paid."}
        </p>
        <BackendForm to={`/f/${c.fid}/expenses/confirm`} csrf={c.s.csrf} className="mt-5 grid gap-4">
          <input type="hidden" name="category" value={c.category} />
          <input type="hidden" name="incurred_on" value={c.incurred_on} />
          <input type="hidden" name="receipt_sha256" value={c.receipt_sha256} />
          <input type="hidden" name="emergency" value={c.emergency} />
          <label className="field">Amount paid (USD)
            <span className="relative">
              <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-2xl font-semibold text-ink-2" aria-hidden>$</span>
              <input name="amount" defaultValue={c.amount} inputMode="decimal" required autoFocus className="!min-h-16 !pl-9 !text-2xl !font-semibold" />
            </span>
          </label>
          <p className="hint m-0">{env.words.categories[c.category] ?? c.category}, paid on {c.incurred_on}.</p>
          <Submit pendingText="Deciding…">Submit expense</Submit>
        </BackendForm>
      </section>
    </>
  );
}

type Cite = { label: string; what: string; quote: string | null; href?: string | null };

export function Decision({ env }: P) {
  const { s, fid, e, d, names, cites = [], payment, paid, can_pay, can_redecide, correction, returned, can_amend } = env.ctx;
  const { words } = env;
  let state: React.ReactNode;
  if (e.status === "reopened") state = <Pill tone="wait">Reopened: payment refunded</Pill>;
  else if (paid) state = <Pill tone="good">Paid, verified with PayPal</Pill>;
  else if (payment?.status === "outside") state = <Pill tone="wait">Settled outside Between, not verified by PayPal</Pill>;
  else state = <Pill tone={d.status === "rejected" ? "bad" : d.status === "payable" ? "info" : "wait"}>{words.status[d.status] ?? d.status}</Pill>;
  return (
    <>
      <PageHead back={{ href: `/f/${fid}`, label: "Home" }}
        title={<ViewTransition name={`exp-${e.id}`}><span>{words.categories[e.category] ?? e.category} · {usd(e.amount_minor)}</span></ViewTransition>}
        lede={<>Paid by <Who role={e.paid_by}>{names[e.paid_by]}</Who> on {e.incurred_on}, requested {e.requested_on}{e.receipt_sha256 ? ". Receipt fingerprint on file." : "."}</>} />

      <div className="grid gap-5 lg:grid-cols-[1fr_1.15fr]">
        <section className="panel flex flex-col gap-4" aria-labelledby="outcome">
          <h2 id="outcome" className="sr-only">Decision</h2>
          <div>{state}</div>
          {e.status === "reopened" ? <p className="m-0">PayPal now shows this payment as refunded or reversed, so it no longer counts as paid.</p> : null}
          {payment?.status === "outside" ? <p className="hint m-0">Synthetic sample history. Only payments made through Between&apos;s PayPal checkout are verified.</p> : null}
          {d.status === "payable" ? (
            <>
              <p className="display m-0 text-[clamp(2.6rem,6vw,3.6rem)]">{usd(d.amount_minor)}</p>
              <p className="m-0 text-[1.08rem]"><Who role={d.owed_by}>{names[d.owed_by]}</Who> owes <Who role={d.owed_to}>{names[d.owed_to]}</Who>{d.due_on ? <span className="text-ink-2">, due {d.due_on}</span> : null}</p>
              {(d.notes ?? []).map((n: Record<string, number>, i: number) => (
                <div key={i} className="grid gap-1">
                  {n.capped_from ? <p className="hint m-0">Capped by the annual limit (would have been {usd(n.capped_from)}).</p> : null}
                  {n.emergency ? <p className="hint m-0">Emergency: tell the other parent within {n.notify_within_hours} hours.</p> : null}
                  {n.fee_added_estimate ? <p className="hint m-0">Includes {usd(n.fee_added_estimate)} for PayPal&apos;s fee (estimate), as you both agreed. The actual fee comes from PayPal after payment.</p> : null}
                  {n.unchecked ? <p className="hint m-0">One deadline in your agreement has no number, so it wasn&apos;t checked.</p> : null}
                </div>
              ))}
            </>
          ) : (
            <>
              <p className="m-0 text-[1.08rem]">{words.reason[d.reason] ?? ""}</p>
              {d.question ? <p className="hint m-0">{d.question} <Link href={`/f/${fid}/rules`}>Answer it on the rules page.</Link></p> : null}
            </>
          )}
          <div className="mt-auto flex flex-wrap gap-2 pt-2">
            {can_pay ? <Link className="btn btn-primary" href={`/f/${fid}/expenses/${e.id}/pay`}>Pay {usd(d.amount_minor)} with PayPal</Link> : null}
            {can_redecide ? <BackendForm to={`/f/${fid}/expenses/${e.id}/redecide`} csrf={s.csrf}><Submit variant="quiet" pendingText="Checking…">Check again</Submit></BackendForm> : null}
          </div>
          <p className="hint m-0 border-t border-line pt-3">Decided by Between&apos;s rules engine from your approved rules. No AI is involved in this decision.</p>
        </section>

        <section className="panel" aria-labelledby="why">
          <h2 id="why" className="h2 mb-4">Why</h2>
          {cites.length ? (
            <ol className="m-0 grid list-none gap-5 p-0">
              {cites.map((c: Cite, i: number) => (
                <li key={i} className="grid gap-2">
                  <p className="m-0 font-semibold">{c.what}</p>
                  {c.quote ? <Clause href={c.href} cite={<>{c.label}: see it in your agreement</>}>{c.quote}</Clause> : <p className="m-0 text-sm text-ink-2">{c.label}</p>}
                  {c.label.startsWith("Resolution") ? <p className="hint m-0">Your working arrangement in Between. It doesn&apos;t change your legal agreement.</p> : null}
                </li>
              ))}
            </ol>
          ) : <p className="m-0 text-ink-2">No clause applies yet.</p>}
        </section>
      </div>

      {payment && payment.status !== "outside" ? (
        <Section title="Payment" className="mt-5">
          <dl className="facts">
            <dt>PayPal status</dt><dd>{payment.status}</dd>
            <dt>Verification</dt><dd>{String(payment.verification).replace("_", " ")}{payment.last_verified_at ? `, ${stamp(payment.last_verified_at)}` : ""}</dd>
            {payment.gross_minor != null ? <>
              <dt>Paid</dt><dd>{usd(payment.gross_minor)}</dd>
              <dt>PayPal fee (from PayPal)</dt><dd>{usd(payment.fee_minor)}</dd>
              <dt>Received</dt><dd>{usd(payment.net_minor)}</dd></> : null}
          </dl>
        </Section>
      ) : null}

      {correction ? (
        <Section title="Correction" className="mt-5">
          {returned ? (
            <><Pill tone="good">Returned, verified with PayPal</Pill>
              <p className="mb-0"><Who role={correction.payer_role}>{names[correction.payer_role]}</Who> sent back {usd(correction.amount_minor)} to <Who role={correction.payee_role}>{names[correction.payee_role]}</Who> after the amount was lowered.</p></>
          ) : s.role === correction.payer_role ? (
            <div className="grid gap-3">
              <p className="m-0 font-semibold">Return {usd(correction.amount_minor)} to {names[correction.payee_role]}</p>
              <p className="hint m-0">The amount was lowered after this was paid, so you received {usd(correction.amount_minor)} more than the share now owed.</p>
              <Link className="btn btn-primary w-fit" href={`/f/${fid}/expenses/${e.id}/return`}>Send {usd(correction.amount_minor)} back with PayPal</Link>
            </div>
          ) : <p className="m-0">Waiting for <Who role={correction.payer_role}>{names[correction.payer_role]}</Who> to send back {usd(correction.amount_minor)} through PayPal.</p>}
        </Section>
      ) : null}

      {can_amend ? (
        <details className="panel mt-5">
          <summary className="cursor-pointer font-semibold">Correct the amount</summary>
          <BackendForm to={`/f/${fid}/expenses/${e.id}/amend`} csrf={s.csrf} className="mt-4 flex flex-wrap items-end gap-3">
            <label className="field">Lower the amount to (USD)<input name="amount" inputMode="decimal" required placeholder="0.00" /></label>
            <Submit variant="quiet">Correct the amount</Submit>
          </BackendForm>
          <p className="hint mb-0">If the share was already paid, the difference is returned through a PayPal checkout the other way.</p>
        </details>
      ) : null}
    </>
  );
}
