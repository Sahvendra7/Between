import { defineConfig, devices } from "@playwright/test";

// E2E_BASE_URL points the suite at a deployment (Vercel preview/production); default is local dev.
export default defineConfig({
  testDir: "tests",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000", trace: "retain-on-failure" },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] }, grep: /@smoke/ },
    { name: "mobile", use: { ...devices["Pixel 7"] }, grep: /@smoke/ },
  ],
});
