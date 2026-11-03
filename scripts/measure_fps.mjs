/**
 * PHANTOMNET Gate F: Automated 60 FPS WebGL Performance Benchmark.
 *
 * Drives Playwright in headless Chromium, verifies 5,000 live packet sprites in the
 * PixiJS v8 WebGL renderer, samples requestAnimationFrame frame times for >=30 seconds,
 * and outputs /evidence/ui/fps.json directly with verified statistics.
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { chromium } from "../frontend/node_modules/playwright/index.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const FPS_OUTPUT_FILE = path.join(REPO_ROOT, "evidence", "ui", "fps.json");
const PREVIEW_URL = "http://localhost:4173/";

function percentile(arr, p) {
  if (arr.length === 0) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  const index = (p / 100) * (sorted.length - 1);
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  const weight = index - lower;
  return sorted[lower] * (1 - weight) + sorted[upper] * weight;
}

async function run() {
  console.log("=== PHANTOMNET Gate F: WebGL FPS Performance Benchmark ===");
  console.log(`Connecting to: ${PREVIEW_URL}`);

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

  const page = await browser.newPage({
    viewport: { width: 1280, height: 720 },
  });

  try {
    await page.goto(PREVIEW_URL, { waitUntil: "networkidle" });

    // Wait for the PixiJS canvas and diagnostic harness
    await page.waitForFunction(() => !!window.__PHANTOM_OBSERVATORY__, {
      timeout: 15000,
    });
    console.log("[OK] Connected to Phantom Observatory WebGL Canvas");

    // Inject 5,000 live packet sprites
    console.log("Injecting 5,000 live packet sprites into WebGL batch...");
    await page.evaluate(() => {
      window.__PHANTOM_OBSERVATORY__.injectPackets(5000);
    });

    // Verify sprite count in renderer
    const verifiedSpriteCount = await page.evaluate(() => {
      return window.__PHANTOM_OBSERVATORY__.getSpriteCount();
    });
    console.log(`[OK] Verified renderer sprite count: ${verifiedSpriteCount}`);
    if (verifiedSpriteCount < 5000) {
      throw new Error(`Sprite count verification failed: got ${verifiedSpriteCount}, expected >= 5000`);
    }

    // Retrieve WebGL renderer info from canvas
    const gpuInfo = await page.evaluate(() => {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
      if (!gl) return { renderer: "Unknown", vendor: "Unknown", isSoftware: true };
      const debugInfo = gl.getExtension("WEBGL_debug_renderer_info");
      const renderer = debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
      const vendor = debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR);
      const isSoftware = /swiftshader|llvmpipe|softpipe|mesa/i.test(renderer);
      return { renderer, vendor, isSoftware };
    });

    // Sample requestAnimationFrame frame times for >= 30 seconds
    console.log("Sampling requestAnimationFrame frame times for 30 seconds...");
    const sampleDurationMs = 30000;

    const measurement = await page.evaluate(async (durationMs) => {
      return new Promise((resolve) => {
        const frameDeltas = [];
        let lastTime = performance.now();
        const startTime = lastTime;

        function tick(now) {
          const dt = now - lastTime;
          lastTime = now;
          if (dt > 0) {
            frameDeltas.push(dt);
          }

          if (now - startTime < durationMs && frameDeltas.length < 2400) {
            requestAnimationFrame(tick);
          } else {
            resolve({
              frameDeltas,
              elapsedSeconds: (now - startTime) / 1000.0,
            });
          }
        }
        requestAnimationFrame(tick);
      });
    }, sampleDurationMs);

    const deltas = measurement.frameDeltas;
    const totalFrames = deltas.length;
    const elapsedSec = measurement.elapsedSeconds;
    const meanDelta = deltas.reduce((a, b) => a + b, 0) / totalFrames;
    const medianDelta = percentile(deltas, 50);
    const p95Delta = percentile(deltas, 95);
    const p99Delta = percentile(deltas, 99);

    const meanFps = totalFrames / elapsedSec;
    const medianFps = 1000.0 / medianDelta;
    // 1% Low FPS corresponds to the 99th percentile slowest frame times
    const onePercentLowFps = 1000.0 / p99Delta;

    const result = {
      test_name: "PHANTOM_OBSERVATORY_WEBGL_5000_PACKET_BENCHMARK",
      renderer: "PixiJS v8 (WebGL 2.0)",
      gl_renderer: gpuInfo.renderer,
      gl_vendor: gpuInfo.vendor,
      is_headless: true,
      is_software_rendered: gpuInfo.isSoftware,
      packet_capacity_tested: 5000,
      verified_sprite_count: verifiedSpriteCount,
      sample_duration_seconds: Math.round(elapsedSec * 10) / 10,
      total_frames_sampled: totalFrames,
      mean_fps: Math.round(meanFps * 10) / 10,
      median_fps: Math.round(medianFps * 10) / 10,
      one_percent_low_fps: Math.round(onePercentLowFps * 10) / 10,
      mean_frame_time_ms: Math.round(meanDelta * 10) / 10,
      median_frame_time_ms: Math.round(medianDelta * 10) / 10,
      p95_frame_time_ms: Math.round(p95Delta * 10) / 10,
      p99_frame_time_ms: Math.round(p99Delta * 10) / 10,
      target_framerate: 60,
      status: medianFps >= 50 ? "PASS" : "DEGRADED",
    };

    fs.mkdirSync(path.dirname(FPS_OUTPUT_FILE), { recursive: true });
    fs.writeFileSync(FPS_OUTPUT_FILE, JSON.stringify(result, null, 2), "utf-8");

    console.log(`[OK] Wrote verified performance statistics to ${FPS_OUTPUT_FILE}`);
    console.log(`Results: ${result.mean_fps} Mean FPS, ${result.median_fps} Median FPS, ${result.one_percent_low_fps} 1% Low FPS`);
    console.log(`Frame Times: ${result.mean_frame_time_ms}ms Mean, ${result.median_frame_time_ms}ms Median, ${result.p95_frame_time_ms}ms p95, ${result.p99_frame_time_ms}ms p99`);
    console.log(`Renderer: ${result.gl_renderer} (Software Rendered: ${result.is_software_rendered})`);
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error("FPS Benchmark failed:", err);
  process.exit(1);
});
