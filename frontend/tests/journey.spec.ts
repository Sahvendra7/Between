import { expect, test } from "@playwright/test";
import { RECEIPT, openDemo, rulesApprovedByBoth, switchParent, watchErrors } from "./helpers";

test("landing page tells the story and opens a demo @smoke", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("settled by the agreement");
  await expect(page.getByRole("heading", { name: "From a clause to a verified payment." })).toBeVisible();
  await expect(page.getByRole("heading", { name: /The AI proposes\. Code decides/ })).toBeVisible();
  const csp = (await page.request.get("/")).headers()["content-security-policy"];
  expect(csp).toContain("script-src 'self' 'nonce-");
  expect(csp).not.toContain("'unsafe-inline' 'strict"); // scripts never allow inline
  const fid = await openDemo(page);
  await expect(page.getByText(/signed in as Mother/)).toBeVisible();
  expect(fid).toMatch(/^[0-9a-f]{12}$/);
  expect(errors).toEqual([]);
});

test("two parents, separate sessions, invite link back to this frontend", async ({ browser, baseURL }) => {
  const a = await (await browser.newContext()).newPage();
  const b = await (await browser.newContext()).newPage();
  await a.goto("/#start");
  await a.getByLabel("How your agreement names you").fill("Mother");
  await a.getByLabel("How it names the other parent").fill("Father");
  await a.getByLabel("Your first name").fill("Ana");
  await a.getByLabel("PayPal account for money owed to you").fill("sb-mother@personal.example.com");
  await a.getByRole("button", { name: "Create our family" }).click();
  const invite = await a.getByLabel("Invite link").inputValue();
  expect(invite.startsWith(new URL(baseURL!).origin + "/join/")).toBe(true); // the backend honoured the allowlisted origin
  const fid = await a.locator("[data-family]").getAttribute("data-family");

  await b.goto(invite);
  await expect(b.getByRole("heading", { name: "Join as Father" })).toBeVisible();
  await b.getByLabel("Your first name").fill("Ben");
  await b.getByLabel("PayPal account for money owed to you").fill("sb-father@personal.example.com");
  await b.getByRole("button", { name: "Join the family" }).click();
  await b.waitForURL(new RegExp(`/f/${fid}$`));
  await expect(b.locator("aside .who").first()).toHaveText("Father");
  await a.goto(`/f/${fid}`);
  await expect(a.locator("aside .who").first()).toHaveText("Mother");

  await b.goto(invite); // single use
  await expect(b.getByRole("heading", { name: "This link can't be used" })).toBeVisible();
  const stranger = await (await browser.newContext()).newPage();
  await stranger.goto(`/f/${fid}`);
  await expect(stranger.getByRole("heading", { name: "Not available to you" })).toBeVisible();
});

test("demo: rules, receipt upload, decision, PayPal hand-off, record, Money & Time", async ({ page }) => {
  test.setTimeout(300_000);
  const errors = watchErrors(page);
  const fid = await openDemo(page);
  await rulesApprovedByBoth(page, fid);

  // the signed-in parent pays an orthodontist bill with a receipt
  await page.goto(`/f/${fid}/expenses/new`);
  await page.getByText("Medical and dental", { exact: true }).first().click();
  await page.locator('input[name="receipt"]').setInputFiles({ name: "receipt.png", mimeType: "image/png", buffer: RECEIPT });
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Confirm the amount" })).toBeVisible({ timeout: 90_000 });
  await page.getByLabel("Amount paid (USD)").fill("420.00");
  await page.getByRole("button", { name: "Submit expense" }).click();
  await page.waitForURL(/\/expenses\/[0-9a-f]+$/);
  const expenseUrl = page.url();
  await expect(page.getByText("Payable")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Why" })).toBeVisible();
  await expect(page.locator(".clause").first()).toBeVisible();

  // the clause link opens the agreement with the quote highlighted
  await page.locator(".clause").first().locator("..").getByRole("link").click();
  await expect(page.locator("mark#clause")).toBeVisible();

  // the other parent owes; they confirm and are handed to the PayPal sandbox (sign-in there stays manual)
  await switchParent(page, fid);
  await page.goto(expenseUrl);
  await page.getByRole("link", { name: /^Pay \$/ }).click();
  await expect(page.getByRole("heading", { name: /^Pay \$/ })).toBeVisible();
  await expect(page.locator("input[name=confirm]:invalid")).toHaveCount(1); // explicit confirmation is required
  await page.getByRole("checkbox").check();
  const toPayPal = page.waitForRequest((r) => r.url().startsWith("https://www.sandbox.paypal.com/"), { timeout: 60_000 });
  await page.getByRole("button", { name: "Continue to PayPal (sandbox)" }).click();
  expect((await toPayPal).url()).toContain("sandbox.paypal.com");

  await page.goto(`/f/${fid}/record`);
  await expect(page.getByText("Record intact")).toBeVisible();
  await expect(page.getByText("payment.created", { exact: false }).first()).toBeVisible();
  await page.getByRole("link", { name: "Export for printing" }).click();
  await expect(page.getByRole("heading", { name: "Between record" })).toBeVisible();

  await page.goto(`/f/${fid}/money`);
  const sample = page.getByRole("button", { name: "Add a sample year (synthetic)" });
  if (await sample.isVisible()) await sample.click();
  await expect(page.locator("#cal .b-calendar, #cal .b-calendarpanel, #cal [class*='b-cal']").first()).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("#studio > *").first()).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("#ledger-fallback tbody tr").first()).toBeVisible();
  await expect(page.locator("#cal .cal-wait")).toBeHidden(); // the calendar itself is on screen, not its placeholder
  await page.waitForTimeout(3000);
  await page.screenshot({ path: "screens/money-1440.png", fullPage: true });
  await page.setViewportSize({ width: 375, height: 812 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  await page.screenshot({ path: "screens/money-375.png", fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });

  await page.goto(`/f/${fid}/calendar`);
  await expect(page.locator("#cal [class*='b-cal']").first()).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "screens/calendar-1440.png", fullPage: true });
  await page.goto(expenseUrl);
  await page.screenshot({ path: "screens/decision-1440.png", fullPage: true });
  expect(errors.filter((e) => !e.includes("sandbox.paypal.com"))).toEqual([]);
});
