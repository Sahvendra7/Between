import { expect, test } from "@playwright/test";
import { RECEIPT, openDemo, rulesApprovedByBoth, switchParent } from "./helpers";

// Manual, headed: a person signs in to the PayPal sandbox and approves. Run with
// MANUAL_PAYPAL=1 E2E_BASE_URL=https://between-app-iota.vercel.app npx playwright test paypal-manual --project=chromium --headed
test.skip(!process.env.MANUAL_PAYPAL, "needs a person at PayPal's sandbox sign-in");

test("real sandbox checkout returns to this frontend and is verified with PayPal", async ({ page, baseURL }) => {
  test.setTimeout(20 * 60_000);
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
  const payer = await page.locator("aside .who").first().textContent();
  await page.getByRole("link", { name: /^Pay \$/ }).click();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Continue to PayPal (sandbox)" }).click();
  await page.waitForURL(/sandbox\.paypal\.com/, { timeout: 60_000 });
  console.log(`\n>>> Sign in to the PayPal sandbox as the ${payer} test account and approve the payment in the browser window.\n`);
  await page.waitForURL((u) => u.href.startsWith(`${baseURL}/pay/return`), { timeout: 15 * 60_000 });
  await expect(page.getByRole("heading", { name: "Verified with PayPal" })).toBeVisible({ timeout: 60_000 });
  console.log(`PASS: ${page.url().split("?")[0]} · ${await page.locator(".facts").innerText()}`);
});
