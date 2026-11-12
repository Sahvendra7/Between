import { Check, ShieldCheck } from "lucide-react";

// Synthetic example throughout: the sample plan for "Maria Rivera" and "David Okafor" in samples/agreements/plan1.
export const STAGES = [
  {
    key: "agreement",
    title: "Your agreement, read once",
    body: "Upload the plan you both signed. An AI proposes a rule for each kind of expense, and every rule must quote its clause word for word. Code checks each quote against your document; anything it can't find is set aside.",
  },
  {
    key: "rules",
    title: "Rules you both approve",
    body: "Each parent approves the exact version, privately. Unclear or contradictory clauses become questions you each answer, never guesses. Change anything and it becomes a new version.",
  },
  {
    key: "decision",
    title: "Every expense decided by code",
    body: "Add a receipt. You confirm the amount; Between's rules engine, with no AI involved, works out who owes what and by when, citing the clause it used.",
  },
  {
    key: "paid",
    title: "Paid, then verified with PayPal",
    body: "The parent who owes confirms and pays the other through a PayPal checkout. Between reads the payment back from PayPal before calling it paid, and chains it into a record neither of you can quietly edit.",
  },
] as const;

export function StageVisual({ stage }: { stage: number }) {
  const card = "rounded-2xl border border-line bg-raised p-5 shadow-[var(--shadow)]";
  if (stage === 0)
    return (
      <div className={`${card} serif text-[0.98rem] leading-[1.7]`}>
        <p className="m-0 mb-3 text-right font-sans text-sm text-ink-2">Page 2</p>
        <p className="m-0 font-semibold">6. Health</p>
        <p className="m-0 mt-2"><span className="font-semibold">6.1 Medical.</span> <mark className="clause-mark">Unreimbursed medical, dental, orthodontic and vision expenses for the Child shall be paid 60% by the Father and 40% by the Mother.</mark></p>
        <p className="m-0 mt-3 text-ink-2">6.2 Neither parent shall incur a non-emergency medical expense over $500 without the other parent&apos;s written consent…</p>
      </div>
    );
  if (stage === 1)
    return (
      <div className={`${card} grid gap-4`}>
        <div className="flex items-center justify-between gap-3"><span className="font-semibold">Rules, version 1</span><span className="pill pill-good">Approved by both</span></div>
        <p className="m-0 text-[1.05rem] font-semibold">Medical and dental: <span className="who who-B">Father</span> 60%, <span className="who who-A">Mother</span> 40%</p>
        <blockquote className="clause !text-[0.93rem]">Unreimbursed medical, dental, orthodontic and vision expenses for the Child shall be paid 60% by the Father and 40% by the Mother.</blockquote>
        <ul className="m-0 grid list-none gap-1.5 p-0 text-[0.95rem]">
          <li className="flex items-center gap-2"><Check size={16} className="text-good" aria-hidden /> <span className="who who-A">Mother</span> approved version 1</li>
          <li className="flex items-center gap-2"><Check size={16} className="text-good" aria-hidden /> <span className="who who-B">Father</span> approved version 1</li>
        </ul>
      </div>
    );
  if (stage === 2)
    return (
      <div className={`${card} grid gap-3`}>
        <p className="m-0 text-sm text-ink-2">Orthodontist, $420.00, paid by <span className="who who-A">Mother</span></p>
        <span className="pill pill-info w-fit">Payable</span>
        <p className="display m-0 text-[3rem]">$252.00</p>
        <p className="m-0"><span className="who who-B">Father</span> owes <span className="who who-A">Mother</span>, due within 14 days</p>
        <p className="m-0 border-t border-line pt-3 text-sm text-ink-2">Because of §6.1 on page 2 and §7.2 on page 3. Decided by the rules engine.</p>
      </div>
    );
  return (
    <div className={`${card} grid gap-4`}>
      <div className="flex items-center gap-3">
        <ShieldCheck size={40} className="text-good" aria-hidden />
        <div><p className="m-0 font-semibold">Verified with PayPal</p><p className="m-0 text-sm text-ink-2">Read back from PayPal before counting</p></div>
      </div>
      <dl className="facts text-[0.95rem]">
        <dt>Paid</dt><dd>$252.00</dd>
        <dt>To</dt><dd><span className="who who-A">Maria</span>, her own PayPal account</dd>
        <dt>Record</dt><dd>A new entry, chained to the one before</dd>
      </dl>
    </div>
  );
}
