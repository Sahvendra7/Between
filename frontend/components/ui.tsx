import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";

export function Mark({ size = 22 }: { size?: number }) {
  // Two households and what sits between them.
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <rect x="3" y="3" width="5" height="18" rx="1.6" fill="var(--a)" />
      <rect x="16" y="3" width="5" height="18" rx="1.6" fill="var(--b)" />
      <circle cx="12" cy="12" r="2" fill="var(--act)" />
    </svg>
  );
}

export function PageHead({ title, lede, back, aside }: { title: ReactNode; lede?: ReactNode; back?: { href: string; label: string }; aside?: ReactNode }) {
  return (
    <header className="mb-7 grid gap-3">
      {back ? (
        <Link href={back.href} className="inline-flex w-fit items-center gap-1.5 text-sm font-semibold no-underline text-ink-2 hover:text-ink">
          <ArrowLeft size={16} aria-hidden /> {back.label}
        </Link>
      ) : null}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="h1">{title}</h1>
        {aside}
      </div>
      {lede ? <p className="lede m-0">{lede}</p> : null}
    </header>
  );
}

export function Pill({ tone, children }: { tone: "good" | "wait" | "bad" | "info"; children: ReactNode }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

export function Who({ role, children }: { role: string; children: ReactNode }) {
  return <span className={`who who-${role}`}>{children}</span>;
}

export function Clause({ children, cite, href }: { children: ReactNode; cite?: ReactNode; href?: string | null }) {
  return (
    <figure className="m-0 grid gap-1.5">
      <blockquote className="clause">{children}</blockquote>
      {cite ? (
        <figcaption className="text-sm text-ink-2">
          {href ? <Link href={href}>{cite}</Link> : cite}
        </figcaption>
      ) : null}
    </figure>
  );
}

export function Section({ title, hint, children, className = "", id }: { title?: ReactNode; hint?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section className={`panel ${className}`} id={id}>
      {title ? <h2 className="h2 mb-1">{title}</h2> : null}
      {hint ? <p className="hint mt-0 mb-4">{hint}</p> : null}
      {children}
    </section>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-line px-5 py-8 text-center">
      <p className="h3">{title}</p>
      {children ? <div className="mt-2 text-ink-2">{children}</div> : null}
    </div>
  );
}
