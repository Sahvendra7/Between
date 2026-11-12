import Link from "next/link";
import type { Envelope } from "@/lib/types";
import { stamp, usd } from "@/lib/format";
import { BackendForm, Submit } from "../backend-form";
import { PageHead, Pill, Section, Who } from "../ui";

type P = { env: Envelope };

function SandboxNote({ name, fee }: { name: string; fee: number }) {
  return (
    <p className="hint">A PayPal sandbox checkout between personal accounts: an Orders API payment, not a Friends and Family transfer.
      PayPal will charge {name} about {usd(fee)} (estimate). The actual fee appears after payment, from PayPal.</p>
  );
}

/** Payment confirmation: deliberately still. One decision, every fact in view, nothing moving. */
export function PayConfirm({ env }: P) {
  const { s, fid, e, d, names, payee, cites = [], fee, decision_hash } = env.ctx;
  const feeNote = (d.notes ?? []).find((n: { fee_added_estimate?: number }) => n.fee_added_estimate);
  return (
    <>
      <PageHead back={{ href: `/f/${fid}/expenses/${e.id}`, label: "Back to the expense" }} title={`Pay ${usd(d.amount_minor)} to ${payee.display_name}`} />
      <section className="sheet max-w-2xl">
        <dl className="facts">
          <dt>For</dt><dd>{env.words.categories[e.category] ?? e.category}, {usd(e.amount_minor)} paid by {names[e.paid_by]} on {e.incurred_on}</dd>
          <dt>Your share</dt><dd>{usd(d.amount_minor)}{d.due_on ? `, due ${d.due_on}` : ""}{feeNote ? `, including ${usd(feeNote.fee_added_estimate)} estimated PayPal fee` : ""}</dd>
          <dt>Goes to</dt><dd><Who role={d.owed_to}>{payee.display_name}</Who> ({payee.label}), their own PayPal account</dd>
          <dt>Because</dt><dd>{cites.map((c: { label: string }) => c.label).join("; ")}</dd>
        </dl>
        <SandboxNote name={payee.display_name} fee={fee} />
        <BackendForm to={`/f/${fid}/expenses/${e.id}/pay`} csrf={s.csrf} className="mt-5 grid gap-4">
          <input type="hidden" name="decision_hash" value={decision_hash} />
          <label className="choice"><input type="checkbox" name="confirm" value="yes" required /> I confirm I&apos;m paying {usd(d.amount_minor)} to {payee.display_name} for this expense</label>
          <Submit pendingText="Opening PayPal…">Continue to PayPal (sandbox)</Submit>
        </BackendForm>
      </section>
    </>
  );
}

export function ReturnConfirm({ env }: P) {
  const { s, fid, e, corr, names, payee, fee } = env.ctx;
  return (
    <>
      <PageHead back={{ href: `/f/${fid}/expenses/${e.id}`, label: "Back to the expense" }} title={`Send ${usd(corr.amount_minor)} back to ${payee.display_name}`} />
      <section className="sheet max-w-2xl">
        <dl className="facts">
          <dt>For</dt><dd>{env.words.categories[e.category] ?? e.category}, now {usd(e.amount_minor)}, paid by {names[e.paid_by]} on {e.incurred_on}</dd>
          <dt>Why</dt><dd>The amount was lowered after the share was paid; this is the difference.</dd>
          <dt>Goes to</dt><dd><Who role={corr.payee_role}>{payee.display_name}</Who> ({payee.label}), their own PayPal account</dd>
        </dl>
        <SandboxNote name={payee.display_name} fee={fee} />
        <BackendForm to={`/f/${fid}/expenses/${e.id}/return`} csrf={s.csrf} className="mt-5 grid gap-4">
          <label className="choice"><input type="checkbox" name="confirm" value="yes" required /> I confirm I&apos;m sending {usd(corr.amount_minor)} back to {payee.display_name}</label>
          <Submit pendingText="Opening PayPal…">Continue to PayPal (sandbox)</Submit>
        </BackendForm>
      </section>
    </>
  );
}

function Seal() {
  return (
    <svg viewBox="0 0 64 64" className="size-16 flex-none" aria-hidden>
      <circle cx="32" cy="32" r="29" fill="var(--good-wash)" stroke="var(--good)" strokeWidth="2.5" />
      <path d="M20 33.5 28.5 42 45 24" fill="none" stroke="var(--good)" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" className="seal-tick" />
    </svg>
  );
}

export function PayResult({ env }: P) {
  const { fid, e, payment, paid } = env.ctx;
  return (
    <>
      <PageHead back={{ href: `/f/${fid}/expenses/${e.id}`, label: "Back to the expense" }}
        title={payment ? (paid ? "Verified with PayPal" : `PayPal status: ${payment.status}`) : "Payment not completed"} />
      {payment ? (
        <section className="sheet max-w-2xl">
          <div className="mb-5 flex items-center gap-4">
            {paid ? <Seal /> : null}
            <div className="grid gap-1">
              {paid ? <Pill tone="good">{payment.kind === "correction" ? "Returned" : "Paid"}, verified with PayPal</Pill> : <Pill tone="wait">Not counted as paid yet</Pill>}
              <p className="m-0 text-ink-2">{paid ? "Between read this payment back from PayPal before counting it." : `Between only counts a payment once PayPal confirms it.${payment.last_error ? ` (${payment.last_error})` : ""}`}</p>
            </div>
          </div>
          <dl className="facts">
            <dt>Paid</dt><dd>{usd(payment.gross_minor)}</dd>
            <dt>PayPal fee (from PayPal)</dt><dd>{usd(payment.fee_minor)}</dd>
            <dt>Received by the other parent</dt><dd>{usd(payment.net_minor)}</dd>
            <dt>PayPal capture</dt><dd className="mono">{payment.capture_id ?? "—"}</dd>
            <dt>Checked</dt><dd>{stamp(payment.last_verified_at)}</dd>
          </dl>
          <p className="hint">PayPal sandbox. Anyone in the family can re-check this payment against PayPal from the record.</p>
        </section>
      ) : null}
      <p className="mt-6"><Link className="btn btn-quiet" href={`/f/${fid}/record`}>Open the record</Link></p>
    </>
  );
}

export { Section };
