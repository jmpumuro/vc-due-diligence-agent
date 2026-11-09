#!/usr/bin/env node
/** Capture README product screenshots that show multi-level diligence value. */
import { chromium } from "playwright";
import { mkdirSync, readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(ROOT, "docs", "media");
const BASE = "http://localhost:3000";

function idFrom(path) {
  if (existsSync(path)) return readFileSync(path, "utf8").trim();
  return "";
}

const L1 = idFrom("/tmp/l1_id.txt") || "1391d594-b946-44ad-9563-9e5a3c16c414";
const L2 = idFrom("/tmp/l2_id.txt") || "dfcf7762-0544-4bd2-b6e2-b4f9070e290b";
const L3 = idFrom("/tmp/l3_id.txt") || "36e3591e-895e-4485-93d1-94fa008b07ed";

if (!L1 || !L2 || !L3) {
  console.error("Need assessment IDs in /tmp/l1_id.txt, /tmp/l2_id.txt, /tmp/l3_id.txt");
  process.exit(1);
}
console.log("capturing L1", L1, "L2", L2, "L3", L3);

const SCENES = [
  ["01-home.png", "/", "Home — pending decisions across levels"],
  ["02-l1-overview.png", `/companies/a/${L1}`, "Level 1 — initial public screen"],
  ["03-l1-findings.png", `/companies/a/${L1}?tab=sources`, "Level 1 — cited findings"],
  ["04-l2-overview.png", `/companies/a/${L2}`, "Level 2 — deeper public diligence"],
  ["05-l2-workstreams.png", `/companies/a/${L2}?tab=domains`, "Level 2 — workstream gates"],
  ["06-l3-overview.png", `/companies/a/${L3}`, "Level 3 — enhanced diligence + partner call"],
  ["07-l3-risks.png", `/companies/a/${L3}?tab=risks`, "Level 3 — risk register from agent gaps"],
  ["08-decisions.png", "/decisions", "Partner decisions queue"],
];

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1.5,
  colorScheme: "light",
});
const page = await context.newPage();

await page.goto(`${BASE}/signin`, { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(600);
const explore = page.getByRole("button", { name: /Explore the demo workspace/i });
if (await explore.count()) {
  await explore.click();
  await page.waitForTimeout(1500);
} else {
  await page.evaluate(async () => {
    await fetch("/api/v1/auth/demo-session", { method: "POST", credentials: "include" });
  });
}

const paths = [];
for (const [filename, path, label] of SCENES) {
  await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2400);
  // Dismiss notification pop if open.
  const close = page.getByRole("button", { name: /^Close$/i });
  if (await close.count()) {
    try {
      await close.first().click({ timeout: 500 });
    } catch {
      /* ignore */
    }
  }
  const dest = join(OUT, filename);
  await page.screenshot({ path: dest, fullPage: false });
  paths.push(dest);
  console.log("wrote", dest.replace(ROOT + "/", ""), "—", label);
}

await browser.close();
console.log(
  "done",
  paths.length,
  "shots — rebuild GIF with: uv run python scripts/capture_readme_media.py",
);
