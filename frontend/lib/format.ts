// Display formatting only. Every amount is computed by the backend's rules engine or read back from PayPal.
const usdFmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
export const usd = (minor: number | null | undefined) => (minor == null ? "—" : usdFmt.format(minor / 100));
export const other = (r: string) => (r === "A" ? "B" : "A");
export const day = (iso?: string | null) =>
  iso ? new Date(iso.length === 10 ? iso + "T12:00:00Z" : iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : "—";
export const stamp = (iso?: string | null) =>
  iso ? new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").toISOString().slice(0, 16).replace("T", " ") + " UTC" : "not yet";
