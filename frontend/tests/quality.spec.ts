import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { openDemo } from "./helpers";

const WIDTHS = [375, 768, 1440];

test("accessibility: no serious or critical axe violations in Between's own UI", async ({ page }) => {
  test.setTimeout(240_000);
  const report: string[] = [];
  const scan = async (label: string) => {
    await page.waitForTimeout(2000); // measure the settled page, not a frame of its entrance
    // AG Studio and Bryntum are third-party widgets; they are reported separately, not hidden
    const r = await new AxeBuilder({ page }).exclude("#studio").exclude("#cal").analyze();
    for (const v of r.violations.filter((v) => v.impact === "serious" || v.impact === "critical"))
      report.push(`${label}: ${v.id} (${v.impact}) ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(", ")}`);
  };
  await page.goto("/"); await scan("landing");
  const fid = await openDemo(page); await scan("home");
  for (const p of ["rules", "agreement", "expenses/new", "record", "calendar", "money"]) { await page.goto(`/f/${fid}/${p}`); await scan(p); }
  console.log(report.join("\n") || "axe: no serious or critical violations");
  expect(report).toEqual([]);
});

for (const scheme of ["light", "dark"] as const) {
  for (const motion of ["no-preference", "reduce"] as const) {
    test(`screenshots ${scheme} ${motion}`, async ({ browser }) => {
      test.setTimeout(240_000);
      const ctx = await browser.newContext({ colorScheme: scheme, reducedMotion: motion });
      const page = await ctx.newPage();
      const fid = await openDemo(page);
      for (const w of WIDTHS) {
        await page.setViewportSize({ width: w, height: w < 500 ? 812 : 900 });
        for (const [name, path] of [["landing", "/"], ["home", `/f/${fid}`], ["rules", `/f/${fid}/rules`], ["expense", `/f/${fid}/expenses/new`], ["record", `/f/${fid}/record`]]) {
          await page.goto(path);
          await page.waitForTimeout(1600); // let the one hero sequence finish
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
          expect(overflow, `${name} @${w} scrolls sideways`).toBeLessThanOrEqual(0);
          await page.screenshot({ path: `screens/${scheme}-${motion}/${name}-${w}.png`, fullPage: name !== "landing" || w === 375 });
        }
      }
      await ctx.close();
    });
  }
}
