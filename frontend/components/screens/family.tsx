import Link from "next/link";
import { ViewTransition } from "react";
import { ArrowRight, Check, Clock, FileUp, MessageCircleQuestion, Plus, Repeat2 } from "lucide-react";
import type { Envelope } from "@/lib/types";
import { other, usd } from "@/lib/format";
import { BackendForm, Submit } from "../backend-form";
import { CopyField, ProofTour, type ProofStep } from "../client-bits";
import { Empty, PageHead, Pill, Section, Who } from "../ui";

type P = { env: Envelope };

export function StartForms({ demo, error }: { demo: boolean; error?: string }) {
  return (
    <div className="grid gap-5 md:grid-cols-[1fr_1.15fr]">
      {demo ? (
        <div className="sheet flex flex-col gap-4 border-transparent bg-ink text-paper">
          <h2 className="h2">Try it as both parents</h2>
          <p className="m-0 text-paper/80">
            Opens your own synthetic family with a sample agreement already read. You can switch between Mother and Father to see each side.
          </p>
          <BackendForm to="/demo/new" className="mt-auto">
            <Submit className="w-full !bg-paper !text-ink" pendingText="Opening your demo family…">Open a demo family</Submit>
          </BackendForm>
        </div>
      ) : null}
      <div className="sheet">
        <h2 className="h2 mb-1">Start your own family</h2>
        <p className="hint mt-0 mb-5">You&apos;ll get a one-time link to send the other parent.</p>
        {error ? <p className="alert alert-bad mb-4" role="alert">{error}</p> : null}
        <BackendForm to="/families" className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="field">How your agreement names you<input name="role_label" required maxLength={40} placeholder="Mother" /></label>
            <label className="field">How it names the other parent<input name="other_label" required maxLength={40} placeholder="Father" /></label>
          </div>
          <label className="field">Your first name<input name="display_name" required maxLength={60} placeholder="Maria" autoComplete="given-name" /></label>
          <label className="field">PayPal account for money owed to you
            <input name="paypal_email" type="email" required placeholder="sb-…@personal.example.com" />
            {demo ? <span className="help">Demo: use a PayPal sandbox personal account.</span> : null}
          </label>
          <Submit pendingText="Creating…">Create our family</Submit>
        </BackendForm>
      </div>
    </div>
  );
}

export function Start({ env }: P) {
  return (
    <>
      <PageHead title="Start with Between" lede="Shared child expenses, settled by the agreement you both signed." />
      <StartForms demo={env.demo_mode} />
    </>
  );
}

export function Join({ env }: P) {
  const { labels = {}, role = "B", token } = env.ctx;
  return (
    <div className="sheet mx-auto max-w-xl">
      <h1 className="h1 mb-2">Join as {labels[role] ?? "the other parent"}</h1>
      <p className="muted mt-0">
        {labels[other(role)]} started a Between family for your child&apos;s shared expenses. This link works once.
      </p>
      <BackendForm to={`/join/${token}`} className="mt-6 grid gap-4">
        <label className="field">Your first name<input name="display_name" required maxLength={60} autoComplete="given-name" /></label>
        <label className="field">PayPal account for money owed to you<input name="paypal_email" type="email" required placeholder="sb-…@personal.example.com" /></label>
        <Submit pendingText="Joining…">Join the family</Submit>
      </BackendForm>
    </div>
  );
}

export function Notice({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="sheet mx-auto max-w-xl">
      <h1 className="h1 mb-3">{title}</h1>
      <p className="muted m-0">{children}</p>
      <p className="mt-6 mb-0"><Link href="/" className="btn btn-quiet">Go to Between</Link></p>
    </div>
  );
}

export const JoinError = ({ env }: P) => <Notice title="This link can't be used">{env.ctx.message}</Notice>;
export const ErrorScreen = ({ env }: P) => <Notice title={env.ctx.title ?? "Something went wrong"}>{env.ctx.detail}</Notice>;

function Balance({ env }: P) {
  const { balance, parents } = env.ctx;
  const rows: [string, string][] = [["paid", "Paid for shared expenses"], ["owed", "Owed to them under your rules"], ["received", "Received, verified with PayPal"]];
  if (balance.rows.A.settled_outside || balance.rows.B.settled_outside) rows.push(["settled_outside", "Settled outside Between (not verified)"]);
  return (
    <section className="panel" aria-labelledby="bal">
      <p id="bal" className="m-0 text-sm font-semibold text-ink-2">{balance.year} so far</p>
      <p className="display mt-2 mb-5 text-[clamp(1.9rem,4vw,2.6rem)]">{balance.line}</p>
      <div className="table-wrap">
        <table className="table">
          <caption className="sr-only">This year&apos;s shared expenses for each parent</caption>
          <thead><tr><th scope="col"><span className="sr-only">Measure</span></th>{(["A", "B"] as const).map((r) => <th key={r} scope="col" className="num"><Who role={r}>{parents[r].label}</Who></th>)}</tr></thead>
          <tbody>
            {rows.map(([k, label]) => (
              <tr key={k}><th scope="row" className="!border-b-line !text-ink-2 font-normal !text-[0.93rem] !whitespace-normal">{label}</th>
                {(["A", "B"] as const).map((r) => <td key={r} className="num font-semibold">{usd(balance.rows[r][k])}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint mb-0">Only payments PayPal confirms count as verified. Synthetic sample history settled outside Between has its own line. Expenses that need both of you, or aren&apos;t shared, aren&apos;t included.</p>
    </section>
  );
}

/** Judge Mode steps. Every fact comes from the backend's own home data; nothing is calculated or invented here. */
function proofSteps(env: Envelope): ProofStep[] {
  const c = env.ctx;
  const { fid, parents, rs } = c;
  const approvals: Record<string, unknown> = c.approvals ?? {};
  const expenses: Record<string, string & number>[] = c.expenses ?? [];
  const rule = (rs.rules as { origin?: string; text?: string; source?: { page?: number; section?: string; quote?: string } }[]).find((r) => r.origin !== "resolution" && r.source?.quote);
  const both = Object.keys(approvals).length === 2;
  const verified = expenses.filter((e) => e.tone === "good");
  const outside = expenses.filter((e) => String(e.label).startsWith("Settled outside"));
  const e = verified[0] ?? expenses.find((x) => x.label === env.words.status?.payable) ?? expenses[0];
  const name = e ? `${env.words.categories[e.category] ?? e.category} · ${usd(e.amount_minor)}` : "";
  const Fact = ({ children }: { children: React.ReactNode }) => <p className="m-0 rounded-xl bg-sunk px-4 py-3"><span className="font-semibold">In this demo family: </span>{children}</p>;
  return [
    { title: "The agreement", href: `/f/${fid}/rules`, cta: "Open the rules and their clauses",
      body: <>
        <p className="m-0">The agreement is the only source of rules. An AI read it once and proposed each rule with a word-for-word quote. Plain code then checked every quote against the document; a rule whose quote isn&apos;t found is set aside.</p>
        {rule?.source ? <blockquote className="clause m-0">{rule.source.quote}<footer className="mt-1 text-sm text-ink-2">{rule.source.page ? `Page ${rule.source.page}, ` : ""}{rule.source.section} · synthetic sample agreement</footer></blockquote> : null}
      </> },
    { title: "The shared decision", href: `/f/${fid}/rules`, cta: "See the approval state",
      body: <>
        <p className="m-0">Nothing is used until both parents approve the exact same version, each in their own session. Unclear clauses become questions answered privately; matching answers are a working arrangement in Between and don&apos;t change the legal agreement.</p>
        <Fact>rules version {rs.version}: {(["A", "B"] as const).map((r) => `${parents[r].label} ${approvals[r] ? "approved" : "has not approved yet"}`).join(", ")}.{both ? "" : " Until both approve, no expense can be decided."}</Fact>
      </> },
    { title: "The expense", href: e ? `/f/${fid}/expenses/${e.id}` : `/f/${fid}/expenses/new`, cta: e ? "Open the decision and its clauses" : "Add an expense",
      body: <>
        <p className="m-0">A parent adds a receipt and confirms the amount. The rules engine, with no AI in it, then decides who owes what and by when, and cites the clauses it used. The same inputs always give the same answer.</p>
        <Fact>{e ? <>{name}, paid by {parents[e.paid_by].label} on {e.incurred_on}. Outcome: {e.label}. Open it to see the amount and the clauses behind it.</> : both ? "no expense yet. Add one to see a decision." : "no expense yet; both parents need to approve the rules first."}</Fact>
      </> },
    { title: "The payment", href: e ? `/f/${fid}/expenses/${e.id}` : `/f/${fid}`, cta: e ? "Open the expense" : "Back to home",
      body: <>
        <p className="m-0">Three different states, never merged: <strong>in progress</strong> (the paying parent confirmed and was sent to PayPal), <strong>captured</strong> (PayPal took the payment), and <strong>verified with PayPal</strong> (Between read the capture back from PayPal and the amount, payee and reference matched). Only the paying parent can start a payment. This walkthrough never does.</p>
        <Fact>{verified.length} payment{verified.length === 1 ? "" : "s"} verified with PayPal (sandbox){outside.length ? `; ${outside.length} sample-history expense${outside.length === 1 ? "" : "s"} marked settled outside Between, not verified by PayPal` : ""}.{e ? ` ${name} is: ${e.label}.` : ""}</Fact>
      </> },
    { title: "The record", href: `/f/${fid}/record`, cta: "Open the record",
      body: <>
        <p className="m-0">Every step above is in a record with its actor, each entry chained to the one before by a hash, so an edit or deletion is detected. Either parent can re-check every payment against PayPal and export the record.</p>
        <p className="m-0">Then see the year: <Link href={`/f/${fid}/money`}>Money &amp; Time</Link> puts the same decisions in an AG Studio report beside a Bryntum calendar of parenting time and payment windows.</p>
      </> },
  ];
}

export function Home({ env }: P) {
  const c = env.ctx;
  const words = env.words;
  const { s, fid, parents, rs } = c;
  const approvals: Record<string, unknown> = c.approvals ?? {};
  const open_questions: unknown[] = c.open_questions ?? [];
  const expenses: Record<string, string & number>[] = c.expenses ?? [];
  const consents: { id: string; text: string; can_agree: boolean }[] = c.consents ?? [];
  const them = parents[other(s.role)];
  const iApproved = Boolean(approvals[s.role]);
  const bothApproved = Object.keys(approvals).length === 2;
  const toAgree = consents.filter((x: { can_agree: boolean }) => x.can_agree);
  const B = parents.B.display_name === "(invited)" ? parents.B.label : parents.B.display_name;
  const next: { href: string; text: string; Icon: typeof Check }[] = [];
  if (!rs) next.push({ href: `/f/${fid}/agreement`, text: "Add your agreement so Between can propose rules", Icon: FileUp });
  else if (!iApproved) next.push({ href: `/f/${fid}/rules`, text: `Review and approve rules version ${rs.version}`, Icon: Check });
  else if (!bothApproved) next.push({ href: `/f/${fid}/rules`, text: `Waiting for ${them.label} to approve version ${rs.version}`, Icon: Clock });
  if (open_questions.length) next.push({ href: `/f/${fid}/rules`, text: `${open_questions.length} open question${open_questions.length === 1 ? "" : "s"} to answer privately`, Icon: MessageCircleQuestion });
  for (const x of toAgree) next.push({ href: "#advance", text: x.text, Icon: MessageCircleQuestion });
  if (bothApproved) {
    // Navigation only: the backend's own label says which expenses are decided but unpaid; the expense page decides who may pay.
    const unpaid = expenses.filter((e) => e.label === words.status?.payable);
    if (!expenses.length) next.push({ href: `/f/${fid}/expenses/new`, text: "Add the first expense: the rules engine decides who owes what, and cites the clause", Icon: Plus });
    for (const e of unpaid.slice(0, 2)) next.push({ href: `/f/${fid}/expenses/${e.id}`, text: `${words.categories[e.category] ?? e.category} · ${usd(e.amount_minor)} is decided and waiting for payment through PayPal`, Icon: Clock });
    if (c.demo_family && expenses.length) next.push({ href: `/f/${fid}/money`, text: "See the year in Money & Time: report, payment calendar and Ledger guide", Icon: ArrowRight });
  }
  return (
    <>
      <div data-family={fid} hidden />
      <PageHead title={<>{parents.A.display_name} <span className="text-ink-2">&amp;</span> {B}</>}
        lede={<>You&apos;re signed in as <Who role={s.role}>{parents[s.role].label}</Who>. Everything below is decided by the rules you both approved.</>} />

      {c.demo_family ? (
        <BackendForm to={`/demo/switch/${fid}`} csrf={s.csrf} className="arrive mb-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-surface px-4 py-3">
          <p className="m-0 text-[0.97rem]"><Repeat2 size={17} className="mr-1.5 inline align-[-3px] text-ink-2" aria-hidden />Demo: see what <Who role={other(s.role)}>{them.label}</Who> sees.</p>
          <Submit variant="quiet" pendingText="Switching…">Switch to {them.label}</Submit>
        </BackendForm>
      ) : null}

      {c.demo_family && rs ? <ProofTour storageKey={`proof-${fid}`} steps={proofSteps(env)} /> : null}

      {c.invite_url ? (
        <Section title={`Invite ${them.label}`} hint="Send this link privately. It opens once and expires in 72 hours." className="mb-5 !bg-act-wash !border-transparent">
          <CopyField value={c.invite_url} label="Invite link" />
        </Section>
      ) : !c.other_joined && !c.demo_family ? (
        <Section className="mb-5">
          <BackendForm to={`/f/${fid}/invite/rotate`} csrf={s.csrf} className="flex flex-wrap items-center justify-between gap-3">
            <p className="m-0">{them.label} hasn&apos;t joined yet.</p>
            <Submit variant="quiet">Make a new invite link</Submit>
          </BackendForm>
        </Section>
      ) : null}

      {next.length ? (
        <section aria-labelledby="next" className="mb-5">
          <h2 id="next" className="sr-only">Next steps</h2>
          <ul className="m-0 grid list-none gap-2 p-0">
            {next.map(({ href, text, Icon }) => (
              <li key={text}>
                <Link href={href} className="group flex min-h-14 items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-3 font-medium text-ink no-underline transition-colors hover:border-act">
                  <span className="grid size-9 flex-none place-items-center rounded-full bg-act-wash text-act"><Icon size={18} aria-hidden /></span>
                  <span className="flex-1">{text}</span>
                  <ArrowRight size={18} aria-hidden className="text-ink-2 transition-transform group-hover:translate-x-0.5" />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
        {c.balance?.any ? <Balance env={env} /> : (
          <section className="panel"><p className="m-0 text-sm font-semibold text-ink-2">This year</p>
            <p className="h2 mt-2">No decided expenses yet</p>
            <p className="hint mb-0">Once an expense is decided under your approved rules, what each of you paid and owes shows here.</p></section>
        )}
        <section className="panel flex flex-col gap-3" aria-labelledby="rules-h">
          <h2 id="rules-h" className="h2">Rules</h2>
          {!rs ? (
            <><p className="m-0 text-ink-2">No agreement yet.</p><Link className="btn btn-primary mt-auto" href={`/f/${fid}/agreement`}>Add your agreement</Link></>
          ) : (
            <>
              <p className="m-0">{bothApproved ? <Pill tone="good">Approved by both · version {rs.version}</Pill> : <Pill tone="wait">Waiting for approval · version {rs.version}</Pill>}</p>
              <ul className="m-0 grid list-none gap-1.5 p-0 text-[0.95rem]">
                {(["A", "B"] as const).map((r) => <li key={r} className="flex items-center justify-between gap-2"><Who role={r}>{parents[r].label}</Who><span className="text-ink-2">{approvals[r] ? "approved" : "not yet"}</span></li>)}
              </ul>
              {open_questions.length ? <p className="hint m-0">{open_questions.length} open question{open_questions.length === 1 ? "" : "s"}: expenses they affect go to both of you.</p> : null}
              <Link href={`/f/${fid}/rules`} className="btn btn-quiet mt-auto">Review the rules</Link>
            </>
          )}
        </section>
      </div>

      <section className="panel mt-5" aria-labelledby="exp-h">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
          <h2 id="exp-h" className="h2">Expenses</h2>
          {rs ? <Link className="btn btn-quiet" href={`/f/${fid}/expenses/new`}><Plus size={17} aria-hidden /> Add an expense</Link> : null}
        </div>
        {expenses.length ? (
          <ul className="m-0 -mx-2 grid list-none p-0">
            {expenses.map((e: Record<string, string & number>) => (
              <li key={e.id} className="border-b border-line last:border-0">
                <Link href={`/f/${fid}/expenses/${e.id}`} className="row-link">
                  <span className="grid gap-0.5">
                    <ViewTransition name={`exp-${e.id}`}><span className="font-semibold">{words.categories[e.category] ?? e.category} · {usd(e.amount_minor)}</span></ViewTransition>
                    <span className="text-sm text-ink-2">Paid by <Who role={e.paid_by}>{parents[e.paid_by].label}</Who> on {e.incurred_on}</span>
                  </span>
                  <span className={`pill pill-${e.tone}`}>{e.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : <Empty title="No expenses yet">{rs ? "Add the first one: Between decides it from your approved rules." : "Add your agreement first."}</Empty>}
      </section>

      {consents.length ? (
        <section className="panel mt-5" id="advance" aria-labelledby="adv-h">
          <h2 id="adv-h" className="h2 mb-3">Agreements in advance</h2>
          <ul className="m-0 grid list-none gap-2 p-0">
            {consents.map((x: { id: string; text: string; can_agree: boolean }) => (
              <li key={x.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-sunk px-4 py-3">
                <span>{x.text}</span>
                {x.can_agree ? <BackendForm to={`/f/${fid}/consents/${x.id}/agree`} csrf={s.csrf}><Submit>Agree</Submit></BackendForm> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
