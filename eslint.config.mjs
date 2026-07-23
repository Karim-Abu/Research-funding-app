// Minimal Next.js-compatible flat ESLint config (Milestone 2).
// Next plugin rules + a TypeScript parser (no TS-specific rules) — intentionally
// lean; no broad style refactors this milestone.
import nextPlugin from "@next/eslint-plugin-next"
import tsParser from "@typescript-eslint/parser"

const config = [
  {
    ignores: [
      "**/.next/**",
      "**/node_modules/**",
      "backend/**",
      "test/**",
      "e2e/**",
      "**/*.config.*",
      "next-env.d.ts",
      // Python-Cache im Repo-Root — nie linten; unter OneDrive zeitweise
      // gesperrt (EPERM beim scandir bricht sonst den ganzen Lint-Lauf ab).
      "**/.pytest_cache/**",
    ],
  },
  {
    files: ["**/*.{js,jsx,ts,tsx,mjs}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: { "@next/next": nextPlugin },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,
      "@next/next/no-img-element": "off",
    },
  },
]

export default config
