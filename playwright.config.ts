import { defineConfig, devices } from "@playwright/test"

// Live smoke test — run the backend (uvicorn :8000) and the frontend
// (APP_BACKEND_MODE=live pnpm dev :3000) first, then: pnpm exec playwright test.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    headless: true,
    trace: "off",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
})
