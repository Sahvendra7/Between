import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { load } from "@/lib/backend";
import { Screen } from "@/components/screens";
import { Notice } from "@/components/screens/family";
import { Shell } from "@/components/shell";

type Props = { params: Promise<{ path: string[] }>; searchParams: Promise<Record<string, string | string[]>> };

const TITLES: Record<string, string> = {
  home: "Home", agreement: "Agreement", rules: "Rules", source: "Clause", expense_new: "New expense", expense_confirm: "Confirm amount",
  decision: "Expense", pay_confirm: "Pay", return_confirm: "Return", pay_result: "Payment", record: "Record", record_export: "Record export",
  calendar: "Calendar", money: "Money & Time", join: "Join", join_error: "Invite link", error: "Not available",
};

async function backendPath({ params, searchParams }: Props) {
  const { path } = await params;
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(await searchParams)) for (const x of [v].flat()) qs.append(k, x);
  return "/" + path.map(encodeURIComponent).join("/") + (qs.size ? `?${qs}` : "");
}

export async function generateMetadata(props: Props): Promise<Metadata> {
  const p = (await props.params).path;
  const sub = p[0] === "f" ? (p[2] === "expenses" ? (p[3] === "new" ? "expense_new" : p[4] === "pay" ? "pay_confirm" : "decision") : p[2] ?? "home") : p[0] === "pay" ? "pay_result" : p[0];
  const title = TITLES[sub];
  return { ...(title ? { title } : {}), robots: { index: false } };
}

/** Every app URL is the backend's own URL: fetch its decision and render the matching screen. */
export default async function Page(props: Props) {
  const out = await load(await backendPath(props));
  if (out.kind === "redirect") redirect(out.location);
  if (out.kind === "page") return <Screen env={out.env} />;
  return (
    <Shell env={{ template: "error", demo_mode: true, viewer: null, words: { categories: {}, status: {}, reason: {} }, ctx: {} }}>
      <Notice title="Between's server is waking up">The backend didn&apos;t answer (status {out.status}). The free server sleeps when idle and takes about a minute to start. Reload this page in a moment.</Notice>
    </Shell>
  );
}
