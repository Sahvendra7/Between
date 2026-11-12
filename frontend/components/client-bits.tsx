"use client";
import { useState } from "react";
import { Check, Copy, Printer } from "lucide-react";

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
