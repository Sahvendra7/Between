"use server";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { backend, outcome, SESSION } from "@/lib/backend";
import { Screen } from "@/components/screens";

/** Every form posts here: forwarded to FastAPI with this browser's session; CSRF tokens travel in the form as before. */
export async function submit(path: string, form: FormData) {
  const body = new FormData();
  for (const [k, v] of form.entries()) {
    if (k.startsWith("$ACTION")) continue;
    if (typeof v !== "string" && v.size === 0) continue; // an empty file input means "no file" (Next names it "undefined")
    body.append(k, v);
  }
  const res = await backend(path, { method: "POST", body });
  for (const line of res.headers.getSetCookie()) {
    const [pair, ...attrs] = line.split(";").map((s) => s.trim());
    const [name, value] = [pair.slice(0, pair.indexOf("=")), pair.slice(pair.indexOf("=") + 1)];
    if (name !== SESSION) continue;
    const age = attrs.find((a) => a.toLowerCase().startsWith("max-age="));
    (await cookies()).set(SESSION, value, {
      httpOnly: true, sameSite: "lax", path: "/", secure: process.env.NODE_ENV === "production",
      ...(age ? { maxAge: Number(age.split("=")[1]) } : {}),
    });
  }
  const out = await outcome(res);
  if (out.kind === "redirect") redirect(out.location);
  if (out.kind === "page") return { node: <Screen env={out.env} /> };
  return { error: "Between's server didn't answer. Nothing was changed. Try again in a minute." };
}
