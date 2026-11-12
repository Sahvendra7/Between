"use client";
import { useEffect } from "react";

type Opts = { script: string; studio?: { src: string; integrity: string } };

/**
 * Runs Between's existing Bryntum / AG Studio scripts (served from the backend's /static) against this page's DOM.
 * They're loaded only on the pages that need them. AG Studio comes from jsDelivr, pinned with SRI, never vendored.
 */
export function VendorMount({ script, studio }: Opts) {
  useEffect(() => {
    let cancelled = false;
    const added: HTMLScriptElement[] = [];
    const add = (src: string, attrs: Record<string, string> = {}) =>
      new Promise<void>((resolve, reject) => {
        const el = document.createElement("script");
        Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
        el.src = src;
        el.onload = () => resolve();
        el.onerror = () => reject(new Error(src));
        document.body.appendChild(el);
        added.push(el);
      });
    (async () => {
      const w = window as unknown as { agStudio?: unknown };
      if (studio && !w.agStudio) await add(studio.src, { integrity: studio.integrity, crossorigin: "anonymous" }).catch(() => undefined);
      if (!cancelled) await add(`${script}?v=${Date.now()}`, { type: "module" }).catch(() => undefined); // fresh run per visit
    })();
    return () => {
      cancelled = true;
      const w = window as unknown as { betweenCalendar?: { destroy?: () => void }; betweenMoney?: { calendar?: { destroy?: () => void } } };
      w.betweenCalendar?.destroy?.();
      w.betweenMoney?.calendar?.destroy?.();
      added.forEach((el) => el.remove());
    };
  }, [script, studio]);
  return null;
}
