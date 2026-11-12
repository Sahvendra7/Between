import { expect, type Page } from "@playwright/test";

// A 1×1 PNG: a synthetic receipt. The AI may read no total from it; the parent then types the amount, as in real use.
export const RECEIPT = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "base64");

export function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    // the dev-only HMR socket and the browser aborting a view transition in a hidden tab are not app errors
    if (m.type() === "error" && !/_next\/hmr|Transition was aborted|hydrat|AG Studio|License|\*{20}/i.test(m.text())) errors.push(m.text());
  });
  page.on("response", (r) => { if (r.status() >= 500) errors.push(`${r.status()} ${r.url()}`); });
  return errors;
}

export async function openDemo(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Open a demo family" }).click();
  await page.waitForURL(/\/f\/[0-9a-f]+$/);
  return page.url().split("/f/")[1];
}

export const signedInAs = (page: Page) => page.locator("aside, header").getByText(/^(Mother|Father)$/).first();

/** Approve every pending version and answer open questions the same way, as the signed-in parent. */
export async function settleRules(page: Page, fid: string) {
  for (let i = 0; i < 4; i++) {
    await page.goto(`/f/${fid}/rules`);
    const approve = page.getByRole("button", { name: /I approve these/ });
    const save = page.getByRole("button", { name: /Save my answer|Change my answer/ }).first();
    if (await approve.isVisible()) { await approve.click(); await page.waitForLoadState("networkidle"); continue; }
    if (await save.isVisible()) {
      await page.getByRole("radio").first().check();
      await save.click();
      await page.waitForLoadState("networkidle");
      continue;
    }
    return;
  }
}

export async function switchParent(page: Page, fid: string) {
  await page.goto(`/f/${fid}`);
  const before = await page.locator("aside .who").first().textContent();
  await page.getByRole("button", { name: /Switch to/ }).click();
  await expect(page.locator("aside .who").first()).not.toHaveText(before ?? "");
}

export async function rulesApprovedByBoth(page: Page, fid: string) {
  for (let round = 0; round < 3; round++) {
    await settleRules(page, fid);
    await switchParent(page, fid);
    await settleRules(page, fid);
    await switchParent(page, fid);
    await page.goto(`/f/${fid}`);
    if (await page.getByText(/Approved by both/).isVisible()) return;
  }
  throw new Error("rules never approved by both");
}
