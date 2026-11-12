import type { Envelope } from "@/lib/types";
import { Shell } from "../shell";
import { ErrorScreen, Home, Join, JoinError, Start } from "./family";
import { Agreement, Rules, Source } from "./rules";
import { Decision, ExpenseConfirm, ExpenseNew } from "./expenses";
import { PayConfirm, PayResult, ReturnConfirm } from "./pay";
import { Record, RecordExport } from "./record";
import { Calendar, Money } from "./time";

const SCREENS: Record<string, (p: { env: Envelope }) => React.ReactNode> = {
  start: Start, join: Join, join_error: JoinError, error: ErrorScreen, home: Home,
  agreement: Agreement, rules: Rules, source: Source,
  expense_new: ExpenseNew, expense_confirm: ExpenseConfirm, decision: Decision,
  pay_confirm: PayConfirm, return_confirm: ReturnConfirm, pay_result: PayResult,
  record: Record, calendar: Calendar, money: Money,
};

/** One backend template → one React screen, inside the workspace shell. */
export function Screen({ env }: { env: Envelope }) {
  if (env.template === "record_export") return <RecordExport env={env} />;
  const C = SCREENS[env.template] ?? ErrorScreen;
  return <Shell env={env} wide={env.template === "money" || env.template === "calendar"}><C env={env} /></Shell>;
}
