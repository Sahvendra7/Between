import Link from "next/link";
import { FileText } from "lucide-react";
import type { Envelope } from "@/lib/types";
import { BackendForm, Submit } from "../backend-form";
import { Clause, PageHead, Pill, Section, Who } from "../ui";

type P = { env: Envelope };
const SAMPLE_TITLES: Record<string, [string, string]> = {
  plan1: ["Clear US plan", "A tidy parenting plan with splits, caps and deadlines."],
  plan2: ["Cross-border plan", "Two countries, two currencies of habit, one set of rules."],
  plan3: ["Messy mediation memo", "Contradictions and gaps that become questions for you both."],
};
const STEPS = [
  ["The AI reads it once", "and proposes rules for each kind of expense."],
  ["Code checks every quote", "word for word against your document. Anything it can't find is set aside."],
  ["Unclear clauses become questions", "that each of you answers privately."],
  ["You both approve the exact version", "Nothing is used until you do."],
];

export function Agreement({ env }: P) {
  const { s, fid, labels, samples = {} } = env.ctx;
  return (
    <>
      <PageHead title="Your agreement" lede={<>Between turns it into rules for <Who role="A">{labels.A}</Who> and <Who role="B">{labels.B}</Who>. The AI proposes; code checks; you two decide.</>} />
      <ol className="m-0 mb-7 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-4" aria-label="How Between reads an agreement">
        {STEPS.map(([a, b], i) => (
          <li key={a} className="rounded-2xl border border-line bg-surface p-4">
            <span className="text-sm font-bold text-act">Step {i + 1}</span>
            <p className="m-0 mt-1 font-semibold leading-snug">{a}</p>
            <p className="m-0 mt-1 text-[0.93rem] text-ink-2">{b}</p>
          </li>
        ))}
      </ol>
      {env.demo_mode ? (
        <Section title="Use a sample agreement" hint="Synthetic documents written for testing. The demo accepts only synthetic agreements." className="mb-5">
          <div className="grid gap-3 sm:grid-cols-3">
            {Object.keys(samples).map((key) => (
              <BackendForm key={key} to={`/f/${fid}/agreement`} csrf={s.csrf} className="contents">
                <input type="hidden" name="sample" value={key} />
                <Submit variant="bare" pendingText="Reading… up to a minute" className="group grid min-h-36 cursor-pointer content-start gap-2 rounded-xl border border-line bg-paper p-4 text-left font-[inherit] text-[1rem] text-ink transition-colors hover:border-act aria-busy:border-act">
                  <FileText size={22} aria-hidden className="text-ink-2 group-hover:text-act" />
                  <span className="block font-semibold">{SAMPLE_TITLES[key]?.[0] ?? key}</span>
                  <span className="block text-sm text-ink-2">{SAMPLE_TITLES[key]?.[1]}</span>
                </Submit>
              </BackendForm>
            ))}
          </div>
          <p className="hint mb-0">Reading takes up to a minute the first time.</p>
        </Section>
      ) : null}
      <Section title={env.demo_mode ? "Or paste or upload one" : "Paste or upload your agreement"}>
        <BackendForm to={`/f/${fid}/agreement`} csrf={s.csrf} className="grid gap-4">
          <label className="field">Agreement text<textarea name="text" rows={10} placeholder={"=== Page 1 ===\n…"} /></label>
          <label className="field">Or a text PDF or .txt file<input type="file" name="file" accept=".txt,.pdf,text/plain,application/pdf" /></label>
          <Submit pendingText="Reading the agreement… up to a minute">Read the agreement</Submit>
        </BackendForm>
      </Section>
    </>
  );
}

type Rule = { id: string; text?: string; kind: string; source: { page: number; section: string; quote: string; question_id?: string } };
type Option = { choice: string; label: string; needs_value?: boolean };

export function Rules({ env }: P) {
  const { s, fid, rs, labels, other, approvals = {}, agreement_rules = [], resolutions = [], questions = [] } = env.ctx;
  const mine = Boolean(approvals[s.role]);
  const optionLabel = (opts: Option[], ch?: string) => opts.find((o) => o.choice === ch)?.label ?? ch;
  return (
    <>
      <PageHead title="Your rules" aside={<Pill tone="info">Version {rs.version}</Pill>}
        lede="Each rule quotes the clause it comes from. The AI proposed them; code checked every quote against your agreement; only what you both approve is used." />

      <section className="panel mb-7 grid gap-5 md:grid-cols-[1fr_auto] md:items-center" aria-labelledby="appr">
        <div>
          <h2 id="appr" className="h2 mb-3">Approval</h2>
          <ul className="m-0 grid list-none gap-2 p-0">
            {(["A", "B"] as const).map((r) => (
              <li key={r} className="flex items-center gap-3"><Who role={r}>{labels[r]}</Who>
                {approvals[r] ? <Pill tone="good">Approved</Pill> : <Pill tone="wait">Not approved yet</Pill>}</li>
            ))}
          </ul>
          <p className="hint mb-0">Version fingerprint <span className="mono">{String(rs.hash).slice(0, 16)}</span>. Any change makes a new version you both approve again.</p>
        </div>
        {!mine ? (
          <BackendForm to={`/f/${fid}/rules/${rs.id}/approve`} csrf={s.csrf}>
            <input type="hidden" name="hash_seen" value={rs.hash} />
            <Submit className="w-full md:w-auto" pendingText="Approving…">I approve these {rs.rules.length} rules</Submit>
          </BackendForm>
        ) : <p className="m-0 text-ink-2">You approved this version.</p>}
      </section>

      {questions.length ? (
        <section className="mb-9" aria-labelledby="qs">
          <h2 id="qs" className="h2">Questions for both of you</h2>
          <p className="hint mb-4">Each of you answers privately. You&apos;ll both see the answers once you&apos;ve both answered. Until you agree, expenses these questions affect go to both of you.</p>
          <div className="grid gap-4">
            {questions.map(({ q, options, resolved_by, answers }: { q: { id: string; question: string; source: { page?: number; section: string } }; options: Option[]; resolved_by?: string; answers: { both_answered?: boolean; mine?: { choice: string; value?: string }; other?: { choice: string; value?: string } } }) => (
              <article key={q.id} className="panel">
                <p className="m-0 text-[1.08rem] font-semibold">{q.question}</p>
                <p className="m-0 mt-1 text-sm text-ink-2">{q.source.page ? `Page ${q.source.page}, ` : ""}{q.source.section}</p>
                <div className="mt-4">
                  {resolved_by ? <Pill tone="good">Settled by resolution {resolved_by}</Pill>
                    : answers.both_answered ? (
                      <div className="grid gap-2">
                        <p className="m-0">You chose: <strong>{optionLabel(options, answers.mine?.choice)}</strong>{answers.mine?.value ? ` (${answers.mine.value} days)` : ""}</p>
                        <p className="m-0" data-other-choice><Who role={other}>{labels[other]}</Who> chose: <strong>{optionLabel(options, answers.other?.choice)}</strong>{answers.other?.value ? ` (${answers.other.value} days)` : ""}</p>
                        <p className="m-0"><Pill tone="wait">You chose differently, so expenses this affects go to both of you</Pill></p>
                      </div>
                    ) : (
                      <BackendForm to={`/f/${fid}/questions/${q.id}/answer`} csrf={s.csrf} className="grid gap-2">
                        <input type="hidden" name="question_id" value={q.id} /><input type="hidden" name="ruleset_id" value={rs.id} />
                        <fieldset className="m-0 grid gap-2 border-0 p-0"><legend className="sr-only">{q.question}</legend>
                          {options.map((o) => (
                            <div key={o.choice} className="grid gap-2">
                              <label className="choice"><input type="radio" name="choice" value={o.choice} required defaultChecked={answers.mine?.choice === o.choice} /> {o.label}</label>
                              {o.needs_value ? <label className="field ml-8 max-w-48">Days<input name="value" inputMode="numeric" pattern="[0-9]*" /></label> : null}
                            </div>
                          ))}
                        </fieldset>
                        <p className="hint m-0">Only you see your answer until {labels[other]} answers too.</p>
                        <Submit variant="quiet" className="w-fit">{answers.mine ? "Change my answer" : "Save my answer"}</Submit>
                      </BackendForm>
                    )}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {resolutions.length ? (
        <section className="mb-9" aria-labelledby="res">
          <h2 id="res" className="h2 mb-3">Working arrangements</h2>
          <div className="grid gap-3">
            {resolutions.map((r: Rule) => (
              <article key={r.id} className="rounded-2xl border border-dashed border-line-strong bg-surface p-4" style={{ borderColor: "var(--line-strong)" }}>
                <p className="m-0 font-semibold">{r.text}</p>
                <p className="m-0 mt-1 text-sm text-ink-2">Resolution {r.id}, answering question {r.source.question_id}. Your working arrangement in Between; it doesn&apos;t change your legal agreement.</p>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section aria-labelledby="from">
        <h2 id="from" className="h2 mb-1">From your agreement</h2>
        <p className="hint mt-0 mb-4">Sans serif is Between&apos;s reading. Serif is your agreement&apos;s own words.</p>
        <ol className="m-0 grid list-none gap-4 p-0">
          {agreement_rules.map((r: Rule) => (
            <li key={r.id} className="panel grid gap-3">
              <p className="m-0 text-[1.06rem] font-semibold">{r.text}</p>
              <Clause href={`/f/${fid}/source?rs=${rs.id}&r=${r.id}#clause`} cite={<>Page {r.source.page}, {r.source.section}: see it in your agreement</>}>{r.source.quote}</Clause>
            </li>
          ))}
        </ol>
        {rs.refused?.length ? (
          <p className="hint">{rs.refused.length} proposal{rs.refused.length === 1 ? "" : "s"} from the AI couldn&apos;t be matched word for word to your agreement, so {rs.refused.length === 1 ? "it was" : "they were"} set aside.</p>
        ) : null}
      </section>
    </>
  );
}

export function Source({ env }: P) {
  const { fid, rule, what, pages = [] } = env.ctx;
  return (
    <>
      <PageHead back={{ href: `/f/${fid}/rules`, label: "Rules" }} title="Where this rule comes from" />
      <section className="panel mb-6 grid gap-2">
        <p className="m-0 text-[1.08rem] font-semibold">{what}</p>
        <p className="m-0 text-sm text-ink-2">Page {rule.source.page}, {rule.source.section}. <a href="#clause">Jump to the highlighted clause</a></p>
        <p className="hint m-0">Between accepted this rule only because this exact text appears on this page under this section. Both of you approved it.</p>
      </section>
      <div className="grid gap-6">
        {pages.map((p: { n: number; body: string; parts: [string, string, string] | null }) => (
          <article key={p.n} aria-label={`Page ${p.n}`} className="mx-auto w-full max-w-[72ch] rounded-md border border-line bg-raised px-[clamp(1.1rem,5vw,3.5rem)] py-[clamp(1.4rem,5vw,3rem)] shadow-[var(--shadow)]">
            <p className="m-0 mb-4 text-right text-sm text-ink-2">Page {p.n}</p>
            <pre className="serif m-0 whitespace-pre-wrap break-words text-[1rem] leading-[1.7]">
              {p.parts ? <>{p.parts[0]}<mark id="clause" className="clause-mark">{p.parts[1]}</mark>{p.parts[2]}</> : p.body}
            </pre>
          </article>
        ))}
      </div>
      <p className="mt-6"><Link href={`/f/${fid}/rules`}>Back to the rules</Link></p>
    </>
  );
}
