/**
 * PHANTOMNET Gate F: Automated 7-Act Demo Scenario Video Recording.
 *
 * Drives Playwright in headless Chromium through the complete 7-act scenario:
 * 1. Handshake Ritual (Noise XX mutual authentication)
 * 2. The Conduit & Fingerprint Strip (raw vs masked flow barcode)
 * 3. The Censor's Eye (inspection scanning, confidence ring, gate-slam)
 * 4. Mask Foundry (parameter morphing & overhead gauge)
 * 5. Arms Race Orrery (orbiting attacker/defender Pareto frontier)
 * 6. Mesh Layer (RouteLab topology rerouting)
 * 7. Time Machine (deterministic episode scrubbing)
 *
 * Records output video directly to /evidence/ui/demo.webm.
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { chromium } from "../frontend/node_modules/playwright/index.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const DEMO_OUTPUT_FILE = path.join(REPO_ROOT, "evidence", "ui", "demo.webm");
const PREVIEW_URL = "http://localhost:4173/";

async function run() {
  console.log("=== PHANTOMNET Gate F: Demo Scenario Video Recording ===");
  console.log(`Target: ${DEMO_OUTPUT_FILE}`);

  const tempVideoDir = path.join(REPO_ROOT, "evidence", "ui", ".tmp_video");
  fs.mkdirSync(tempVideoDir, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: [
      "--enable-webgl",
      "--ignore-gpu-blocklist",
      "--use-gl=angle",
      "--use-angle=default",
      "--no-sandbox",
    ],
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: {
      dir: tempVideoDir,
      size: { width: 1280, height: 720 },
    },
  });

  const page = await context.newPage();

  try {
    await page.goto(PREVIEW_URL, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);

    // Act 1: Handshake Ritual
    console.log("Act 1: Handshake Ritual...");
    await page.waitForTimeout(4000);

    // Act 2: Fingerprint Barcode & Conduit
    console.log("Act 2: Fingerprint Barcode & Conduit...");
    await page.waitForTimeout(5000);

    // Act 3: Censor's Eye & Gate Slam
    console.log("Act 3: Censor's Eye & Gate Slam...");
    await page.waitForTimeout(5000);

    // Act 4: Mask Foundry Lens
    console.log("Act 4: Activating Mask Foundry Lens...");
    const foundryBtn = await page.$("button:has-text('FOUNDRY')");
    if (foundryBtn) await foundryBtn.click();
    await page.waitForTimeout(5000);

    // Act 5: Arms Race Orrery Lens
    console.log("Act 5: Activating Arms Race Orrery Lens...");
    const orreryBtn = await page.$("button:has-text('ORRERY')");
    if (orreryBtn) await orreryBtn.click();
    await page.waitForTimeout(5000);

    // Act 6: Mesh Lens
    console.log("Act 6: Activating Mesh Topology Lens...");
    const meshBtn = await page.$("button:has-text('MESH')");
    if (meshBtn) await meshBtn.click();
    await page.waitForTimeout(5000);

    // Act 7: Time Machine & Evidence Wall
    console.log("Act 7: Time Machine scrubbing & Evidence Wall...");
    const evidenceBtn = await page.$("button:has-text('EVIDENCE')");
    if (evidenceBtn) await evidenceBtn.click();
    await page.waitForTimeout(4000);

    console.log("Demo execution complete. Finalizing recording...");
  } finally {
    await page.close();
    await context.close();
    await browser.close();
  }

  // Find the recorded video file in tempVideoDir and move to DEMO_OUTPUT_FILE
  const files = fs.readdirSync(tempVideoDir);
  const videoFile = files.find((f) => f.endsWith(".webm") || f.endsWith(".mp4"));

  if (videoFile) {
    const srcPath = path.join(tempVideoDir, videoFile);
    fs.copyFileSync(srcPath, DEMO_OUTPUT_FILE);
    fs.rmSync(tempVideoDir, { recursive: true, force: true });
    const stat = fs.statSync(DEMO_OUTPUT_FILE);
    console.log(`[OK] Successfully saved demo video to ${DEMO_OUTPUT_FILE} (${stat.size} bytes)`);
  } else {
    throw new Error("No video file was produced by Playwright");
  }
}

run().catch((err) => {
  console.error("Demo recording failed:", err);
  process.exit(1);
});
