import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { RECEIPT, openDemo, rulesApprovedByBoth, switchParent } from "./helpers";

// Local dev only: signs in to the PayPal *sandbox* with the test account in spike/.env and approves the checkout.
// Run: PAYPAL_LOCAL=1 npx playwright test paypal-local --project=chromium --headed
test.skip(!process.env.PAYPAL_LOCAL, "opt-in: real PayPal sandbox calls");
test.use({ trace: "off", screenshot: "off", video: "off" }); // keep the sandbox password out of artefacts

function sandboxAccount(role: "A" | "B") {
  const env = Object.fromEntries(readFileSync(join(__dirname, "../../../spike/.env"), "utf8").split("\n")
    .filter((l) => l.includes("=") && !l.trimStart().startsWith("#")).map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim()]));
  return { email: env[`PARENT_${role}_EMAIL`], password: env[`PARENT_${role}_PASSWORD`] };
}

async function approveInSandbox(page: Page, account: { email: string; password: string }) {
  const email = page.locator("#email");
  await email.waitFor({ timeout: 60_000 });
  await email.fill(account.email);
  const next = page.locator("#btnNext");
  if (await next.isVisible()) await next.click();
  await page.locator("#password").fill(account.password);
  await page.locator("#btnLogin").click();
  const pay = page.locator("#payment-submit-btn, button[data-testid='submit-button-initial']").or(page.getByRole("button", { name: /Complete Purchase|Pay Now|Continue to Review Order|^Pay$/ })).first();
  await pay.waitFor({ timeout: 90_000 });
  await pay.click();
}

test("local: sandbox checkout, PayPal returns to the Next.js origin, Between verifies it", async ({ page, baseURL }) => {
  test.setTimeout(10 * 60_000);
  expect(baseURL, "this spec only runs against a local dev server").toMatch(/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/);
  const fid = await openDemo(page);
  await rulesApprovedByBoth(page, fid);
  await page.goto(`/f/${fid}/expenses/new`);
  await page.getByText("Medical and dental", { exact: true }).first().click();
  await page.locator('input[name="receipt"]').setInputFiles({ name: "receipt.png", mimeType: "image/png", buffer: RECEIPT });
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Amount paid (USD)").fill("420.00");
  await page.getByRole("button", { name: "Submit expense" }).click();
  await page.waitForURL(/\/expenses\/[0-9a-f]+$/);
  const expense = page.url();
  await switchParent(page, fid);
  await page.goto(expense);
  const payer = (await page.locator("aside .who").first().textContent()) === "Father" ? "B" : "A";
  await page.getByRole("link", { name: /^Pay \$/ }).click();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Continue to PayPal (sandbox)" }).click();
  await page.waitForURL(/^https:\/\/www\.sandbox\.paypal\.com\//, { timeout: 60_000 });
  await approveInSandbox(page, sandboxAccount(payer));
  await page.waitForURL((u) => u.href.startsWith(`${baseURL}/pay/return`), { timeout: 3 * 60_000 });
  await expect(page.getByRole("heading", { name: "Verified with PayPal" })).toBeVisible({ timeout: 60_000 });
  const capture = (await page.locator(".facts dd.mono").textContent())?.trim();
  console.log(`PASS on ${new URL(page.url()).origin}: capture ${capture}; ${(await page.locator(".facts").innerText()).replace(/\n/g, " | ")}`);
  await page.goto(`/f/${fid}/record`);
  await expect(page.getByText("Record intact")).toBeVisible();
  await expect(page.locator("table").first()).toContainText(capture ?? "missing");
});
