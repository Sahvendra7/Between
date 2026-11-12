"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Check, Copy, Printer } from "lucide-react";

export function CopyField({ value, label }: { value: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="flex flex-wrap gap-2">
      <input className="input mono min-w-0 flex-1" readOnly value={value} aria-label={label} onFocus={(e) => e.currentTarget.select()} />
      <button type="button" className="btn btn-primary" onClick={async () => { await navigator.clipboard.writeText(value); setDone(true); setTimeout(() => setDone(false), 2000); }}>
        {done ? <Check size={17} aria-hidden /> : <Copy size={17} aria-hidden />}<span aria-live="polite">{done ? "Copied" : "Copy link"}</span>
      </button>
    </div>
  );
}

export function PrintButton() {
  return <button type="button" className="btn btn-primary no-print" onClick={() => window.print()}><Printer size={17} aria-hidden /> Print or save as PDF</button>;
}

export type ProofStep = { title: string; body: React.ReactNode; href: string; cta: string };

/** Judge Mode: a read-only walkthrough. It only shows what the server already sent and links to real screens. */
export function ProofTour({ steps, storageKey }: { steps: ProofStep[]; storageKey: string }) {
  const [i, setI] = useState(-1); // -1 = closed
  useEffect(() => {
    try { const v = Number(sessionStorage.getItem(storageKey)); if (v >= 1 && v <= steps.length) setI(v - 1); } catch {}
  }, [storageKey, steps.length]);
  const go = (n: number) => { setI(n); try { sessionStorage.setItem(storageKey, String(n + 1)); } catch {} };
  const open = i >= 0;
  const step = open ? steps[i] : null;
  const last = i === steps.length - 1;
  return (
    <section className="panel mb-5 !border-act/40" aria-labelledby="proof-h">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="proof-h" className="h2">Judge Mode: follow the proof</h2>
          <p className="hint m-0 mt-1">Five steps, about 90 seconds. Read-only: it shows this synthetic demo family&apos;s own data and changes nothing.</p>
        </div>
        {open
          ? <button type="button" className="btn btn-quiet" onClick={() => go(-1)}>Exit</button>
          : <button type="button" className="btn btn-primary" onClick={() => go(0)}>Start the walkthrough</button>}
      </div>
      {step ? (
        <div className="mt-5 border-t border-line pt-5">
          <ol className="m-0 mb-4 flex list-none flex-wrap gap-1.5 p-0" aria-label="Walkthrough steps">
            {steps.map((s, n) => (
              <li key={s.title}>
                <button type="button" onClick={() => go(n)} aria-current={n === i ? "step" : undefined}
                  className={`min-h-9 rounded-full border px-3 text-sm font-medium ${n === i ? "border-act bg-act-wash text-act" : "border-line bg-surface text-ink-2"}`}>
                  {n + 1}<span className="sr-only sm:not-sr-only">. {s.title}</span>
                </button>
              </li>
            ))}
          </ol>
          <div aria-live="polite">
            <p className="m-0 text-sm font-semibold text-ink-2">Step {i + 1} of {steps.length}</p>
            <h3 className="h2 mt-1 mb-3">{step.title}</h3>
            <div className="grid gap-3 text-[0.97rem]">{step.body}</div>
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Link href={step.href} className="btn btn-quiet">{step.cta} <ArrowRight size={16} aria-hidden /></Link>
            <span className="flex-1" />
            <button type="button" className="btn btn-quiet" onClick={() => go(i - 1)} disabled={i === 0}>Back</button>
            {last
              ? <button type="button" className="btn btn-primary" onClick={() => go(0)}>Replay</button>
              : <button type="button" className="btn btn-primary" onClick={() => go(i + 1)}>Next</button>}
          </div>
        </div>
      ) : null}
    </section>
  );
}
