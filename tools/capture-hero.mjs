import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const scenes = ["trace", "avatars", "cameras", "alerts", "fps", "reports", "poise"];
const outDir = path.join(root, "website/public/images/hero");
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 980, height: 860 },
  deviceScaleFactor: 2,
});

for (const scene of scenes) {
  await page.goto(`http://127.0.0.1:5173/capture.html#${scene}`, {
    waitUntil: "networkidle",
  });
  const frame = page.locator("[data-capture-frame]");
  await frame.waitFor({ state: "visible" });
  await page.waitForTimeout(scene === "trace" ? 900 : 400);
  await frame.screenshot({
    path: path.join(outDir, `${scene}.png`),
    type: "png",
    omitBackground: true,
  });
  console.log(`wrote ${scene}.png`);
}

await browser.close();
