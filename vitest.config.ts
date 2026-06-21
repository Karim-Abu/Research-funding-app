import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"
import { dirname } from "node:path"
import { fileURLToPath } from "node:url"

const root = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": root },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test/setup.ts"],
    include: ["test/**/*.test.{ts,tsx}"],
    environmentOptions: { jsdom: { url: "http://localhost:3000" } },
  },
})
