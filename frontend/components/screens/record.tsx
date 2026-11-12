import Link from "next/link";
import { Link2, ShieldAlert, ShieldCheck } from "lucide-react";
import type { Envelope } from "@/lib/types";
import { stamp, usd } from "@/lib/format";
import { BackendForm, Submit } from "../backend-form";
import { PrintButton } from "../client-bits";
import { Empty, PageHead, Pill, Section } from "../ui";

type P = { env: Envelope };
type Pay = Record<string, string & number>;
type Ev = { seq: number; at: string; who: string; type: string; body: Record<string, string>; hash: string };

const verdict = (p: Pay) => p.status === "outside" ? <Pill tone="wait">Settled outside Between</Pill>
  : p.verification === "verified" ? <Pill tone="good">Verified</Pill>
  : p.verification === "refunded" || p.verification === "reversed" ? <Pill tone="wait">{p.verification}</Pill>
  : <Pill tone="info">{String(p.verification).replace("_", " ")}</Pill>;

export function Record({ env }: P) {
  const { s, fid, events = [], payments = [], broken_at, names } = env.ctx;
  const latest = events.slice(-5);
  return (
    <>
      <PageHead title="Record" lede="Every decision, approval and payment, each entry chained to the one before it. If anything is edited, removed or reordered later, the chain shows where." />
      <section className={`panel mb-6 grid gap-5 ${broken_at ? "!border-bad" : ""} md:grid-cols-[auto_1fr] md:items-center`} aria-live="polite">
        <div className="flex items-center gap-3">
          {broken_at ? <ShieldAlert size={36} className="text-bad" aria-hidden /> : <ShieldCheck size={36} className="text-good" aria-hidden />}
          <div>
            <p className="h2">{broken_at ? `Changed at entry ${broken_at}` : "Record intact"}</p>
            <p className="m-0 text-sm text-ink-2">{broken_at ? "An entry was edited, removed or reordered after it was written." : `${events.length} entries, each chained to the one before.`}</p>
          </div>
        </div>
        <ol className="m-0 flex list-none flex-wrap items-center gap-1 p-0 md:justify-end" aria-label="The latest links in the chain">
          {latest.map((e: Ev, i: number) => (
            <li key={e.seq} className="flex items-center gap-1">
              {i ? <Link2 size={14} className="text-ink-2" aria-hidden /> : null}
              <span className="mono rounded-md bg-sunk px-2 py-1 text-[0.78rem]" title={`Entry ${e.seq}: ${e.type}`}>#{e.seq} {e.hash.slice(0, 6)}</span>
            </li>
          ))}
        </ol>
      </section>

      <Section title="Payments, as PayPal reports them" className="mb-6">
        {payments.length ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th scope="col">Payment</th><th scope="col">From → to</th><th scope="col">Status</th><th scope="col">Verified</th><th scope="col" className="num">Paid</th><th scope="col" className="num">Fee</th><th scope="col" className="num">Received</th></tr></thead>
                <tbody>
                  {payments.map((p: Pay) => (
                    <tr key={p.id}>
                      <td className="mono">{p.capture_id || p.order_id || p.id}</td>
                      <td>{names[p.payer_role]} → {names[p.payee_role]}{p.kind === "correction" ? <span className="block text-sm text-ink-2">correction</span> : null}</td>
                      <td>{p.status}</td>
                      <td>{verdict(p)}{p.last_verified_at ? <span className="block text-sm text-ink-2">{stamp(p.last_verified_at)}</span> : null}</td>
                      <td className="num">{usd(p.gross_minor)}</td><td className="num">{usd(p.fee_minor)}</td><td className="num">{usd(p.net_minor)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <BackendForm to={`/f/${fid}/record/verify`} csrf={s.csrf} className="mt-4">
              <Submit pendingText="Checking with PayPal…">Check every payment with PayPal now</Submit>
            </BackendForm>
          </>
        ) : <Empty title="No payments yet">Payments appear here once a parent pays through PayPal.</Empty>}
      </Section>

      <Section title="Everything that happened">
        <ol className="m-0 grid list-none p-0">
          {events.map((e: Ev) => (
            <li key={e.seq} className="grid grid-cols-[3rem_1fr] gap-x-3 gap-y-0.5 border-b border-line py-3 last:border-0 sm:grid-cols-[3rem_10rem_1fr_auto]">
              <span className="mono text-ink-2">#{e.seq}</span>
              <span className="text-sm text-ink-2 sm:order-none">{stamp(e.at)}</span>
              <span className="col-start-2 sm:col-start-auto"><strong className="font-semibold">{e.who}</strong> <span className="mono">{e.type}</span>
                {e.body?.to ? <> → {e.body.to}</> : null}{e.body?.status ? <span className="text-ink-2"> · {e.body.status}</span> : null}</span>
              <span className="mono col-start-2 text-ink-2 sm:col-start-auto">{e.hash.slice(0, 12)}</span>
            </li>
          ))}
        </ol>
        <p className="mt-4 mb-0"><Link className="btn btn-quiet" href={`/f/${fid}/record/export`}>Export for printing</Link></p>
      </Section>
    </>
  );
}

export function RecordExport({ env }: P) {
  const { fid, generated, events = [], payments = [], broken_at, names } = env.ctx;
  return (
    <main className="mx-auto max-w-5xl bg-surface px-6 py-10 text-[0.95rem]">
      <div className="no-print mb-6 flex flex-wrap gap-3"><PrintButton /><Link className="btn btn-quiet" href={`/f/${fid}/record`}>Back to the record</Link></div>
      <h1 className="h1">Between record</h1>
      <p><strong>Not legal advice. Sandbox demonstration.</strong> Synthetic data; PayPal sandbox only. Approving rules in Between doesn&apos;t change any legal agreement.</p>
      <p className="text-ink-2">Family {fid}, {names.A} and {names.B}, generated {stamp(generated)}</p>
      <p>{broken_at ? `Chain check: changed at entry ${broken_at}.` : `Chain check: intact (${events.length} entries).`}</p>
      <h2 className="h2 mt-8 mb-2">Payments</h2>
      <table className="table"><thead><tr><th>PayPal capture</th><th>From → to</th><th>Status</th><th>Verified</th><th className="num">Paid</th><th className="num">Fee</th><th className="num">Received</th></tr></thead><tbody>
        {payments.map((p: Pay) => <tr key={p.id}><td className="mono">{p.capture_id || "—"}</td><td>{names[p.payer_role]} → {names[p.payee_role]}</td><td>{p.status}</td><td>{p.verification} {p.last_verified_at ? stamp(p.last_verified_at) : ""}</td><td className="num">{usd(p.gross_minor)}</td><td className="num">{usd(p.fee_minor)}</td><td className="num">{usd(p.net_minor)}</td></tr>)}
      </tbody></table>
      <h2 className="h2 mt-8 mb-2">Entries</h2>
      <table className="table"><thead><tr><th>#</th><th>When (UTC)</th><th>Who</th><th>What</th><th>Hash</th></tr></thead><tbody>
        {events.map((e: Ev) => <tr key={e.seq}><td>{e.seq}</td><td className="whitespace-nowrap">{e.at.replace("T", " ").slice(0, 19)}</td><td>{e.who}</td><td className="mono">{e.type}</td><td className="mono">{e.hash}</td></tr>)}
      </tbody></table>
      <p className="hint">Each entry&apos;s hash covers the entry and the hash before it. Each payment can be re-read from PayPal by its capture id.</p>
    </main>
  );
}
