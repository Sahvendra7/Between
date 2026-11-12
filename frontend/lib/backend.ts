import "server-only";
import { cookies, headers } from "next/headers";
import type { Envelope } from "./types";

const BACKEND = new URL(process.env.BETWEEN_BACKEND_URL ?? "http://127.0.0.1:8000");
export const SESSION = "between_session";

export type Outcome =
  | { kind: "redirect"; location: string }
  | { kind: "page"; status: number; env: Envelope }
  | { kind: "down"; status: number };

/** The browser-facing origin, so the backend can point invite links and PayPal's return URL back here. */
async function publicOrigin() {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "";
  const proto = h.get("x-forwarded-proto") ?? (host.startsWith("localhost") || host.startsWith("127.") ? "http" : "https");
  return `${proto}://${host}`;
}

/** One request to FastAPI on behalf of this browser: its session cookie in, the backend's decision out. */
export async function backend(path: string, init: { method?: string; body?: FormData } = {}) {
  if (!path.startsWith("/") || path.startsWith("//")) throw new Error("bad path");
  const url = new URL(path, BACKEND);
  if (url.origin !== BACKEND.origin) throw new Error("bad path"); // never fetch anywhere but the backend
  const sid = (await cookies()).get(SESSION)?.value;
  const res = await fetch(url, {
    method: init.method ?? "GET",
    body: init.body,
    redirect: "manual",
    cache: "no-store",
    headers: {
      "x-between-json": "1",
      "x-between-origin": await publicOrigin(),
      ...(sid ? { cookie: `${SESSION}=${sid}` } : {}),
    },
  });
  return res;
}

export async function outcome(res: Response): Promise<Outcome> {
  if (res.status >= 300 && res.status < 400) {
    const loc = new URL(res.headers.get("location") ?? "/", BACKEND);
    // the backend's own pages map 1:1 onto this frontend; anything else (PayPal) stays absolute
    return { kind: "redirect", location: loc.origin === BACKEND.origin ? loc.pathname + loc.search + loc.hash : loc.href };
  }
  if ((res.headers.get("content-type") ?? "").includes("application/json")) {
    const env = (await res.json()) as Envelope;
    if (env && typeof env.template === "string") return { kind: "page", status: res.status, env };
  }
  return { kind: "down", status: res.status };
}

export async function load(path: string) {
  try {
    return await outcome(await backend(path));
  } catch {
    return { kind: "down", status: 503 } as Outcome;
  }
}
