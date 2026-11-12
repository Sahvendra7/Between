import Link from "next/link";
import { ViewTransition, type ReactNode } from "react";
import { Plus } from "lucide-react";
import type { Envelope } from "@/lib/types";
import { Mark } from "./ui";
import { SideNav, TabBar } from "./nav";
import { FocusAlert } from "./backend-form";

export function DemoStrip() {
  return (
    <p className="no-print m-0 bg-ink px-4 py-1.5 text-center text-[0.8rem] font-medium text-paper">
      Sandbox demonstration with synthetic data. No real money moves. Not legal advice.
    </p>
  );
}

/** The workspace around every signed-in screen: who you are, which family, where you can go. */
export function Shell({ env, children, wide = false }: { env: Envelope; children: ReactNode; wide?: boolean }) {
  const v = env.viewer;
  const error = env.ctx.error as string | undefined;
  const body = (
    <>
      {error ? (
        <p className="alert alert-bad mb-6" role="alert" tabIndex={-1} data-page-alert>
          {error}
        </p>
      ) : null}
      {error ? <FocusAlert /> : null}
      {children}
    </>
  );
  if (!v) {
    return (
      <div className="min-h-dvh">
        {env.demo_mode ? <DemoStrip /> : null}
        <header className="mx-auto flex max-w-5xl items-center px-5 py-5">
          <Link href="/" className="flex items-center gap-2 text-lg font-bold text-ink no-underline"><Mark /> Between</Link>
        </header>
        <main id="main" className="mx-auto max-w-2xl px-5 pb-20">{body}</main>
      </div>
    );
  }
  const base = `/f/${v.fid}`;
  const me = v.names[v.role];
  const them = v.names[v.role === "A" ? "B" : "A"];
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[264px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2">Skip to content</a>
      <aside className="no-print sticky top-0 hidden h-dvh flex-col gap-6 border-r border-line bg-surface px-4 py-5 lg:flex">
        <Link href={base} className="flex items-center gap-2 px-2 text-lg font-bold text-ink no-underline"><Mark /> Between</Link>
        <div className={`who-${v.role} rounded-xl border border-line bg-paper p-3`}>
          <p className="m-0 text-xs font-medium text-ink-2">Signed in as</p>
          <p className="m-0 mt-0.5"><span className={`who who-${v.role}`}>{me}</span>{v.me && v.me !== "(invited)" ? <span className="text-ink-2"> · {v.me}</span> : null}</p>
          <p className="m-0 mt-1 text-sm text-ink-2">Sharing with <span className={`who who-${v.role === "A" ? "B" : "A"} font-medium`}>{them}</span></p>
        </div>
        <nav aria-label="Family"><SideNav fid={v.fid} /></nav>
        <Link href={`${base}/expenses/new`} className="btn btn-primary"><Plus size={18} aria-hidden /> New expense</Link>
        {env.demo_mode ? (
          <p className="mt-auto rounded-xl bg-sunk p-3 text-[0.82rem] leading-snug text-ink-2">
            Sandbox demonstration with synthetic data. PayPal sandbox only; no real money moves. Not legal advice.
          </p>
        ) : null}
      </aside>
      <div className="min-w-0">
        {env.demo_mode ? <div className="lg:hidden"><DemoStrip /></div> : null}
        <header className="no-print sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-line bg-paper/90 px-4 py-3 backdrop-blur lg:hidden">
          <Link href={base} className="flex items-center gap-2 font-bold text-ink no-underline"><Mark size={20} /> Between</Link>
          <div className="flex items-center gap-2">
            <span className={`who who-${v.role} rounded-full border border-line bg-surface px-3 py-1 text-sm`} aria-label={`Signed in as ${me}`}>{me}</span>
            <Link href={`${base}/expenses/new`} className="btn btn-primary !min-h-10 !px-3" aria-label="New expense"><Plus size={18} aria-hidden /></Link>
          </div>
        </header>
        <main id="main" className={`mx-auto px-4 pb-28 pt-7 sm:px-6 lg:px-10 lg:pb-16 lg:pt-10 ${wide ? "max-w-[1240px]" : "max-w-[920px]"}`}>
          <ViewTransition name="page">{body}</ViewTransition>
        </main>
        <footer className="no-print mx-auto max-w-[920px] px-4 pb-28 text-sm text-ink-2 sm:px-6 lg:px-10 lg:pb-10">
          Between coordinates shared child expenses. It doesn&apos;t give legal advice, and approving rules here doesn&apos;t change your legal agreement.
        </footer>
      </div>
      <TabBar fid={v.fid} />
    </div>
  );
}
