import type { Metadata } from "next";
import Link from "next/link";
import { ArrowDown, Bot, Cpu, Landmark } from "lucide-react";
import { Mark } from "@/components/ui";
import { DemoStrip } from "@/components/shell";
import { StartForms } from "@/components/screens/family";
import { ScrollStory } from "@/components/landing/scroll-story";
import { YearPreview } from "@/components/landing/year-preview";

export const metadata: Metadata = { title: { absolute: "Between · shared child expenses, by the agreement" } };
const DEMO = process.env.BETWEEN_DEMO_MODE !== "0";

function Hero() {
  return (
    <section className="mx-auto grid max-w-[1240px] gap-12 px-5 pt-10 pb-20 sm:px-8 lg:grid-cols-[1.08fr_1fr] lg:items-center lg:gap-16 lg:pt-16 lg:pb-28">
      <div className="grid gap-7">
        <h1 className="display m-0 text-[clamp(2.9rem,7.2vw,5.6rem)]">
          Shared child expenses, settled by the agreement you both signed.
        </h1>
        <p className="lede m-0 !text-[1.22rem]">
          For separated parents. Between reads your co-parenting agreement, turns it into rules you both approve, decides each expense by those rules, and settles it through PayPal, then checks PayPal to confirm it.
        </p>
        <div className="flex flex-wrap gap-3">
          <a href="#start" className="btn btn-primary !min-h-12 !px-5">Try the demo</a>
          <a href="#how" className="btn btn-quiet !min-h-12 !px-5"><ArrowDown size={18} aria-hidden /> How it works</a>
        </div>
      </div>
      <HeroArtifact />
    </section>
  );
}

/** The opening moment: a clause is highlighted, and the decision it produces settles on top of it. Plays once. */
function HeroArtifact() {
  return (
    <div className="relative mx-auto w-full max-w-[540px] pb-16" aria-label="Example with the synthetic sample agreement: clause 6.1 splits medical costs 60/40, so on a $420 orthodontist bill the Father owes the Mother $252, verified with PayPal." role="img">
      <div className="hero-doc serif rounded-md border border-line bg-raised px-7 py-8 text-[1rem] leading-[1.75] shadow-[var(--shadow)] sm:px-9">
        <p className="m-0 mb-2 font-sans text-xs text-ink-2">Parenting plan, page 2 · synthetic sample</p>
        <p className="m-0 font-semibold">6. Health</p>
        <p className="m-0 mt-2"><span className="font-semibold">6.1 Medical.</span>{" "}
          <span className="hero-mark">Unreimbursed medical, dental, orthodontic and vision expenses for the Child shall be paid 60% by the Father and 40% by the Mother.</span></p>
        <p className="m-0 mt-3 text-ink-2">6.2 Neither parent shall incur a non-emergency medical expense over $500 without the other parent&apos;s written consent.</p>
      </div>
      <div className="hero-card absolute right-[-4px] bottom-0 left-10 rounded-2xl border border-line bg-surface p-5 shadow-[0_30px_60px_-30px_rgb(21_32_43/0.55)] sm:left-auto sm:w-[340px]">
        <div className="flex items-center justify-between gap-3"><span className="text-sm text-ink-2">Orthodontist · $420.00</span><span className="pill pill-good">Verified</span></div>
        <p className="display m-0 mt-2 text-[2.4rem]">$252.00</p>
        <p className="m-0 text-[0.97rem]"><span className="who who-B">Father</span> paid <span className="who who-A">Mother</span> under §6.1</p>
      </div>
    </div>
  );
}

const ROLES = [
  { Icon: Bot, who: "The AI", does: ["Reads your agreement once and proposes rules", "Reads the total on a receipt for you to confirm", "Answers questions in the Ledger guide from what's already decided"], never: "Never decides an amount, approves a rule, or moves money." },
  { Icon: Cpu, who: "Between's code", does: ["Checks every quoted clause word for word", "Decides each expense from the rules you both approved", "Chains every event into a tamper-evident record"], never: "Never guesses: unclear clauses become questions for you both." },
  { Icon: Landmark, who: "PayPal", does: ["Runs the checkout the paying parent confirms", "Pays the other parent's own account", "Is asked again before anything counts as paid"], never: "Sandbox only in this demo; no real money moves." },
];

export default function Landing() {
  return (
    <div className="overflow-x-clip">
      {DEMO ? <DemoStrip /> : null}
      <header className="mx-auto flex max-w-[1240px] items-center justify-between px-5 py-5 sm:px-8">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold text-ink no-underline"><Mark /> Between</Link>
        <nav aria-label="Page" className="flex items-center gap-1 sm:gap-4">
          <a href="#how" className="hidden px-2 text-[0.97rem] font-medium text-ink-2 no-underline hover:text-ink sm:inline">How it works</a>
          <a href="#ai" className="hidden px-2 text-[0.97rem] font-medium text-ink-2 no-underline hover:text-ink sm:inline">Safety</a>
          <a href="#start" className="btn btn-quiet !min-h-10">Try the demo</a>
        </nav>
      </header>
      <main>
        <Hero />

        <section className="border-y border-line bg-surface">
          <div className="mx-auto grid max-w-[1240px] gap-8 px-5 py-16 sm:px-8 md:grid-cols-[1fr_1.4fr] md:py-24">
            <h2 className="display m-0 text-[clamp(2rem,4vw,3rem)]">Most arguments aren&apos;t about the money.</h2>
            <div className="grid gap-4 text-[1.12rem] text-ink-2">
              <p className="m-0">They&apos;re about what the agreement means. Who pays for braces? Was that camp agreed? Has last month&apos;s share been paid, or is it &ldquo;on its way&rdquo;?</p>
              <p className="m-0 text-ink">Between gives both parents the same answer, with the clause it comes from and a payment PayPal has confirmed. Neither of you has to be the one who says so.</p>
            </div>
          </div>
        </section>

        <section id="how" className="mx-auto max-w-[1240px] px-5 py-20 sm:px-8 md:py-28" aria-labelledby="how-h">
          <h2 id="how-h" className="display m-0 mb-4 max-w-[18ch] text-[clamp(2.2rem,4.6vw,3.6rem)]">From a clause to a verified payment.</h2>
          <p className="lede mb-10">One expense, followed all the way through. The example uses Between&apos;s synthetic sample agreement.</p>
          <ScrollStory />
        </section>

        <section id="ai" className="bg-ink text-paper" aria-labelledby="ai-h">
          <div className="mx-auto max-w-[1240px] px-5 py-20 sm:px-8 md:py-28">
            <h2 id="ai-h" className="display m-0 max-w-[20ch] text-[clamp(2.2rem,4.6vw,3.6rem)]">The AI proposes. Code decides. You approve.</h2>
            <p className="mt-5 mb-12 max-w-[62ch] text-[1.15rem] text-paper/75">Three parts, three different jobs. Nothing that moves money depends on what a language model says.</p>
            <div className="grid gap-px overflow-hidden rounded-2xl bg-paper/15 md:grid-cols-3">
              {ROLES.map(({ Icon, who, does, never }) => (
                <div key={who} className="grid content-start gap-4 bg-ink p-6">
                  <Icon size={26} aria-hidden className="text-paper/70" />
                  <h3 className="m-0 text-[1.35rem] font-bold">{who}</h3>
                  <ul className="m-0 grid list-disc gap-2 pl-5 text-paper/85 marker:text-paper/40">{does.map((d) => <li key={d}>{d}</li>)}</ul>
                  <p className="m-0 border-t border-paper/15 pt-4 text-[0.97rem] text-paper/70">{never}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto grid max-w-[1240px] gap-12 px-5 py-20 sm:px-8 md:py-28 lg:grid-cols-[1fr_1.1fr] lg:items-center" aria-labelledby="mt-h">
          <div className="grid gap-5">
            <h2 id="mt-h" className="display m-0 text-[clamp(2.1rem,4.2vw,3.2rem)]">Money &amp; Time: the year on one screen.</h2>
            <p className="lede m-0">Whose week it is, what was spent, what&apos;s due and by when, and how much of each cap is left. Ask the Ledger guide why a share is what it is, and it answers with the clause, without changing anything.</p>
            <ul className="m-0 grid list-none gap-2 p-0 text-[1.02rem]">
              <li><span className="who who-A">Mother&apos;s weeks</span> and <span className="who who-B">Father&apos;s weeks</span> from the agreement</li>
              <li>Payment windows from request to due date</li>
              <li>Swap requests the other parent agrees to</li>
            </ul>
          </div>
          <div className="sheet"><YearPreview /></div>
        </section>

        <section className="border-y border-line bg-surface" aria-labelledby="trust-h">
          <div className="mx-auto grid max-w-[1240px] gap-10 px-5 py-20 sm:px-8 md:grid-cols-3 md:py-24">
            <h2 id="trust-h" className="display m-0 text-[clamp(2rem,3.6vw,2.8rem)] md:col-span-1">Built to be checked.</h2>
            <dl className="m-0 grid gap-8 sm:grid-cols-2 md:col-span-2">
              {[
                ["Every rule cites its clause", "Open any rule and Between shows the exact sentence, highlighted on its page."],
                ["Both parents approve one exact version", "Approvals are tied to a fingerprint of the rules. Change a word and it's a new version."],
                ["Paid means PayPal said so", "A payment counts only after Between reads it back from PayPal. Refunds reopen the expense."],
                ["A record that shows tampering", "Each entry is chained to the one before, so an edit or deletion shows where it happened."],
              ].map(([t, d]) => <div key={t} className="grid gap-1.5"><dt className="text-[1.1rem] font-bold">{t}</dt><dd className="m-0 text-ink-2">{d}</dd></div>)}
            </dl>
          </div>
        </section>

        <section id="start" className="mx-auto max-w-[1240px] px-5 py-20 sm:px-8 md:py-28" aria-labelledby="start-h">
          <h2 id="start-h" className="display m-0 mb-3 text-[clamp(2.2rem,4.6vw,3.6rem)]">See it for yourself.</h2>
          <p className="lede mb-10">The demo uses synthetic families and the PayPal sandbox. Nothing you do here moves real money.</p>
          <StartForms demo={DEMO} />
        </section>
      </main>
      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-4 px-5 py-8 text-sm text-ink-2 sm:px-8">
          <span className="flex items-center gap-2"><Mark size={18} /> Between coordinates shared child expenses. It isn&apos;t legal advice, and approving rules here doesn&apos;t change your legal agreement.</span>
          <span>Built for the PayPal AI hackathon. MIT licensed.</span>
        </div>
      </footer>
    </div>
  );
}
