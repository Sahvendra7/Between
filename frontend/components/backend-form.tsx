"use client";
import { createContext, use, useEffect, useState, type ReactNode, type ComponentProps } from "react";
import { usePathname } from "next/navigation";
import { useFormStatus } from "react-dom";
import { submit } from "@/app/actions";

const Slot = createContext<(n: ReactNode) => void>(() => {});

/** Shows a page the backend rendered in answer to a form (a next step or a correction) in place of the current one. */
export function ScreenSlot({ children }: { children: ReactNode }) {
  const [shown, setShown] = useState<{ path: string; node: ReactNode } | null>(null);
  const path = usePathname();
  const show = (node: ReactNode) => {
    setShown({ path, node });
    window.scrollTo({ top: 0 });
  };
  return <Slot value={show}>{shown && shown.path === path ? shown.node : children}</Slot>;
}

type Props = Omit<ComponentProps<"form">, "action" | "encType" | "method"> & { to: string; csrf?: string };

/** A form that posts to the backend path `to`. Works the same with or without the Next.js router state. */
export function BackendForm({ to, csrf, children, ...rest }: Props) {
  const show = use(Slot);
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      {...rest}
      action={async (fd) => {
        setError(null);
        const r = await submit(to, fd);
        if (r && "node" in r) show(r.node);
        else if (r && "error" in r) setError(r.error ?? null);
      }}
    >
      {csrf ? <input type="hidden" name="csrf" value={csrf} /> : null}
      {children}
      {error ? <p className="alert alert-bad mt-3" role="alert">{error}</p> : null}
    </form>
  );
}

export function Submit({ children, variant = "primary", className = "", name, value, pendingText }:
  { children: ReactNode; variant?: "primary" | "quiet" | "plain" | "bare"; className?: string; name?: string; value?: string; pendingText?: string }) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" name={name} value={value} className={variant === "bare" ? className : `btn btn-${variant} ${className}`} disabled={pending} aria-busy={pending}>
      {pending ? <span className="spinner" aria-hidden /> : null}
      <span>{pending && pendingText ? pendingText : children}</span>
    </button>
  );
}

/** Focus the page's alert when a screen arrives with one, so screen readers hear it. */
export function FocusAlert() {
  useEffect(() => {
    document.querySelector<HTMLElement>("[data-page-alert]")?.focus();
  }, []);
  return null;
}
