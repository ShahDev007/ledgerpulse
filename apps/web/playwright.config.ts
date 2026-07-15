import { defineConfig, devices } from "@playwright/test";

// Runs against the already-running dev stack (make dev). Install browsers first:
//   pnpm --filter @ledgerpulse/web exec playwright install chromium
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: {
    baseURL: process.env.WEB_URL || "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
