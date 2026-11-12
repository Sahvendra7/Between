import Link from "next/link";
import type { Envelope } from "@/lib/types";
import { usd } from "@/lib/format";
import { BackendForm, Submit } from "../backend-form";
import { VendorMount } from "../vendor-mount";
import { Clause, Empty, PageHead, Pill, Section, Who } from "../ui";

type P = { env: Envelope };
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function BryntumStyles() {
  return (
    <>
      <link rel="stylesheet" href="/static/vendor/fontawesome/css/fontawesome.min.css" precedence="vendor" />
      <link rel="stylesheet" href="/static/vendor/fontawesome/css/solid.min.css" precedence="vendor" />
      <link rel="stylesheet" href="/static/vendor/bryntum/calendar.css" precedence="vendor" />
      <link rel="stylesheet" href="/static/vendor/bryntum/svalbard-light.css" media="(prefers-color-scheme: light)" precedence="vendor-theme" />
      <link rel="stylesheet" href="/static/vendor/bryntum/svalbard-dark.css" media="(prefers-color-scheme: dark)" precedence="vendor-theme" />
    </>
  );
}

function CalendarFrame({ id = "cal", label, className = "", data }: { id?: string; label: string; className?: string; data?: Record<string, string> }) {
  return (
    <div id={id} className={`calendar ${className}`} aria-label={label} role="region"
      {...Object.fromEntries(Object.entries(data ?? {}).map(([k, v]) => [`data-${k}`, v]))}>
      <p className="cal-wait" aria-hidden>Loading the calendar…</p>
    </div>
  );
}

export function Calendar({ env }: P) {
  const { s, fid, sched, names, swaps = [], today } = env.ctx;
  const them = s.role === "A" ? "B" : "A";
  return (
    <>
      <BryntumStyles />
      <PageHead title="Calendar" lede="Parenting time from your agreement, with expenses on the days they were paid." />
      {!sched ? (
        <p className="panel mb-6">Your agreement has no regular week-on, week-off pattern Between could read, so only expenses are shown.</p>
      ) : (
        <div className="mb-6 grid gap-5 lg:grid-cols-2">
          <Section title="Parenting time">
            <p className="mt-0"><Who role="A">{names.A}</Who> and <Who role="B">{names.B}</Who> alternate weeks, changing over on {DAYS[sched.changeover_weekday]}s at {sched.changeover_time}.</p>
            <Clause cite={`Page ${sched.source.page}, ${sched.source.section}`}>{sched.source.quote}</Clause>
            <BackendForm to={`/f/${fid}/calendar/anchor`} csrf={s.csrf} className="mt-4 flex flex-wrap items-center gap-2">
              <span className="mr-1">This week the child is with</span>
              <Submit variant="quiet" name="parent" value="A">{names.A}</Submit>
              <Submit variant="quiet" name="parent" value="B">{names.B}</Submit>
            </BackendForm>
            <p className="hint mb-0">{sched.anchor_date ? <>Set {sched.set_by ? `by ${names[sched.set_by] ?? "the demo"}` : "for the demo"}: week starting {sched.anchor_date} with {names[sched.first_parent]}.</> : "The agreement doesn't say who has which week, so tell Between once."}</p>
          </Section>
          {sched.anchor_date ? (
            <Section title="Swap days" hint={`Drag across days in ${names[them]}'s time on the calendar, or choose dates here. ${names[them]} agrees or declines. An agreed swap is an arrangement between you; it doesn't change your parenting plan.`}>
              <BackendForm to={`/f/${fid}/calendar/swaps`} csrf={s.csrf} id="swap-form" className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
                <label className="field">From<input type="date" name="start" min={today} required /></label>
                <label className="field">Until (not including)<input type="date" name="end" min={today} required /></label>
                <Submit variant="quiet">Ask for these days</Submit>
              </BackendForm>
              {swaps.length ? (
                <ul className="m-0 mt-4 grid list-none gap-2 p-0">
                  {swaps.map((w: Record<string, string>) => {
                    const o = w.requested_by === "A" ? "B" : "A";
                    return (
                      <li key={w.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-sunk px-3 py-2">
                        <span><Who role={w.requested_by}>{names[w.requested_by]}</Who>: {w.start_date} to {w.end_date} (not including)</span>
                        {w.status === "accepted" ? <Pill tone="good">Agreed by {names[o]}</Pill> : s.role === o ? (
                          <span className="flex gap-2">
                            <BackendForm to={`/f/${fid}/calendar/swaps/${w.id}/accept`} csrf={s.csrf}><Submit>Agree</Submit></BackendForm>
                            <BackendForm to={`/f/${fid}/calendar/swaps/${w.id}/decline`} csrf={s.csrf}><Submit variant="quiet">Decline</Submit></BackendForm>
                          </span>
                        ) : (
                          <span className="flex items-center gap-2"><Pill tone="wait">Waiting for {names[o]}</Pill>
                            <BackendForm to={`/f/${fid}/calendar/swaps/${w.id}/cancel`} csrf={s.csrf}><Submit variant="plain">Withdraw</Submit></BackendForm></span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              ) : null}
            </Section>
          ) : null}
        </div>
      )}
      <CalendarFrame label="Parenting time and expenses calendar"
        data={{ src: `/f/${fid}/calendar.json`, swaps: sched?.anchor_date ? "yes" : "", other: names[them] }} />
      <p className="hint">Calendar by Bryntum Calendar Community (MIT).</p>
      <VendorMount script="/static/calendar.js" />
    </>
  );
}

type Cap = { categoryName: string; party: string; partyName: string; cap: number; used: number; left: number; clause: string };

export function Money({ env }: P) {
  const { s, fid, feed, approved, demo_family, studio_src, studio_sri, license, ai_enabled } = env.ctx;
  const windows = feed.obligations.filter((o: { kind: string }) => o.kind === "pay-window");
  const count = (st: string) => windows.filter((o: { state: string }) => o.state === st).length;
  return (
    <>
      <BryntumStyles />
      <PageHead title="Money & Time"
        lede="Your agreement over the year: what each of you paid, what's due and by when, how much of each cap is left, and which clause says so." />
      {!approved ? (
        <Empty title="Approve your rules to see your year"><p className="m-0">Between decides each expense only from rules you&apos;ve both approved. <Link href={`/f/${fid}/rules`}>Review the rules</Link></p></Empty>
      ) : (
        <>
          {demo_family && !feed.expenses.length ? (
            <section className="sheet mb-6 grid gap-4 !border-transparent bg-act-wash md:grid-cols-[1fr_auto] md:items-center">
              <p className="m-0">This demo family has no history yet. Add a synthetic year of expenses, each decided by Between&apos;s rules engine under your approved rules. Past payments are marked as settled outside Between, never as verified by PayPal.</p>
              <BackendForm to={`/f/${fid}/money/sample-year`} csrf={s.csrf}><Submit pendingText="Adding the year…">Add a sample year (synthetic)</Submit></BackendForm>
            </section>
          ) : null}

          <dl className="mb-6 grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-4">
            {([["Expenses this year", feed.expenses.length], ["Payment windows open", count("open")], ["Overdue", count("overdue")], ["Verified with PayPal", count("verified")]] as const).map(([k, v]) => (
              <div key={k} className="grid gap-1 bg-surface p-4">
                <dt className="text-sm text-ink-2">{k}</dt><dd className="display m-0 text-[2rem]">{v}</dd>
              </div>
            ))}
          </dl>

          {feed.caps.length ? (
            <Section title="Annual caps" hint="From your agreement. Used amounts come from expenses Between has decided this year." className="mb-6">
              <ul className="m-0 grid list-none gap-4 p-0 md:grid-cols-2">
                {feed.caps.map((c: Cap) => {
                  const pct = c.cap ? Math.min(100, Math.round((c.used / c.cap) * 100)) : 0; // bar width only
                  return (
                    <li key={c.categoryName + c.party} className="grid gap-1.5">
                      <div className="flex flex-wrap items-baseline justify-between gap-2"><span><Who role={c.party}>{c.partyName}</Who>, {c.categoryName}</span><span className="text-sm text-ink-2">{c.clause}</span></div>
                      <div className="h-2.5 overflow-hidden rounded-full bg-sunk" role="img" aria-label={`${usd(c.used * 100)} of ${usd(c.cap * 100)} used`}>
                        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: `var(--${c.party.toLowerCase()})` }} />
                      </div>
                      <p className="m-0 text-sm text-ink-2">{usd(c.used * 100)} used of {usd(c.cap * 100)}; {usd(c.left * 100)} left</p>
                    </li>
                  );
                })}
              </ul>
            </Section>
          ) : null}

          <h2 className="h2 mb-2">The year on the calendar</h2>
          <CalendarFrame className="money-cal" label="Parenting time, expenses and payment windows" />
          <p className="hint">Bars show each payment window, from the day it was asked for to the day it&apos;s due under your agreement. Select an expense or a window to focus the report on it.</p>

          <div className="mt-8 mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="h2">Report{ai_enabled ? " and Ledger guide" : ""}</h2>
            <div className="flex gap-2"><button type="button" id="studio-clear" className="btn btn-quiet" hidden>Show the whole year</button><button type="button" id="studio-mode" className="btn btn-quiet" hidden>Edit report</button></div>
          </div>
          {ai_enabled ? (
            <>
              <input type="hidden" id="csrf" value={s.csrf} />
              <p className="hint mt-0">The Ledger guide answers from what Between already decided. It can explain, preview and point at the calendar. It can&apos;t approve rules, change them, or move money.</p>
            </>
          ) : null}
          <div id="studio" className="studio" data-src={`/f/${fid}/money.json`} data-fid={fid} data-license={license} data-ai={ai_enabled ? "1" : ""} aria-label="Your year: report, ledger and guide" role="region" />

          <Section title="Ledger" className="mt-6" id="ledger-fallback">
            {feed.expenses.length ? (
              <div className="table-wrap">
                <table className="table">
                  <caption className="sr-only">Every shared expense this year</caption>
                  <thead><tr><th scope="col">Date</th><th scope="col">Category</th><th scope="col">Paid by</th><th scope="col" className="num">Amount</th><th scope="col">Status</th></tr></thead>
                  <tbody>{feed.expenses.map((e: Record<string, string & number>) => (
                    <tr key={e.id}><td className="whitespace-nowrap">{e.date}</td><td>{e.categoryName}</td><td><Who role={e.paidBy}>{e.paidByName}</Who></td><td className="num">{usd(e.amountMinor)}</td><td><Link href={e.href}>{e.label}</Link></td></tr>
                  ))}</tbody>
                </table>
              </div>
            ) : <Empty title="No expenses yet"><Link href={`/f/${fid}/expenses/new`}>Add your first expense</Link></Empty>}
          </Section>
          <p className="hint">Calendar by Bryntum Calendar Community (MIT). Report by AG Studio (AG Grid), loaded from jsDelivr. Amounts come from Between&apos;s rules engine and PayPal; nothing here is computed by AI.</p>
          <VendorMount script="/static/money.js" studio={{ src: studio_src, integrity: studio_sri }} />
        </>
      )}
    </>
  );
}
