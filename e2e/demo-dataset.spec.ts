import { execFileSync } from "node:child_process"
import { existsSync } from "node:fs"
import path from "node:path"
import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"

test.skip(
  process.env.DEMO_DATA_ENABLED !== "true",
  "Set DEMO_DATA_ENABLED=true to seed and run the live demo dataset flow."
)

test.beforeAll(() => {
  const backendDir = path.join(process.cwd(), "backend")
  const venvPython = path.join(backendDir, ".venv", "Scripts", "python.exe")
  const python = process.env.BACKEND_PYTHON ?? (existsSync(venvPython) ? venvPython : "python")
  execFileSync(python, ["-m", "app.demo.seed", "--reset"], {
    cwd: backendDir,
    env: {
      ...process.env,
      APP_ENV: "development",
      DEMO_DATA_ENABLED: "true",
    },
    stdio: "inherit",
  })
})

test("M6.1 seeded demo dashboard, draft continuation, and open requirements", async ({
  page,
}) => {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  await expect(page.getByText(/Verbundwerkstoffe \(Demo\)/)).toBeVisible({
    timeout: 20_000,
  })
  await expect(page.getByText(/Produktionsanlagen \(Demo\)/)).toBeVisible()
  // Each project card carries a single primary-action button ("Weiterarbeiten");
  // the per-project next_action (continue_draft vs review_analysis) is asserted via
  // the API below. Both demo projects expose the action.
  await expect(page.getByRole("button", { name: "Weiterarbeiten" }).first()).toBeVisible()
  expect(
    await page.getByRole("button", { name: "Weiterarbeiten" }).count()
  ).toBeGreaterThanOrEqual(2)
  await expect(page.getByRole("button", { name: "Review freigeben" })).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Export erstellen" })).toHaveCount(0)

  const projects = (await (await page.request.get("/api/projects")).json()).items as Array<{
    project_id: string
    title: string
    workflow_summary: { next_action: string; current_step: number }
  }>
  const projectA = projects.find((project) => project.title.includes("Verbundwerkstoffe"))
  const projectB = projects.find((project) => project.title.includes("Produktionsanlagen"))
  expect(projectA?.workflow_summary).toMatchObject({
    next_action: "continue_draft",
    current_step: 5,
  })
  expect(projectB?.workflow_summary).toMatchObject({
    next_action: "review_analysis",
    current_step: 3,
  })
  expect(projectA).toBeTruthy()
  expect(projectB).toBeTruthy()

  const runsA = (await (
    await page.request.get(`/api/projects/${projectA!.project_id}/runs`)
  ).json()).items as Array<{ run_id: string; status: string }>
  const runA = runsA.find((run) => run.status === "completed")!.run_id
  const fieldsA = (await (await page.request.get(`/api/runs/${runA}/fields`)).json()) as Array<{
    current_version: { created_by: string }
    evidence_links: Array<{ status: string }>
  }>
  expect(fieldsA.filter((field) => field.current_version.created_by === "user").length).toBeGreaterThanOrEqual(2)
  expect(
    fieldsA.flatMap((field) => field.evidence_links).filter((link) => link.status === "active").length
  ).toBeGreaterThanOrEqual(2)

  await page.getByText(/Verbundwerkstoffe \(Demo\)/).click()
  await expect(page).toHaveURL(/\/editor/, { timeout: 20_000 })
  await expect(page.getByText("Strukturvorlage").first()).toBeVisible({
    timeout: 20_000,
  })
  // The evidence panel is a tab — open "Belege" to see the linkage section
  // ("Verknüpfte Belege"). Active links for this run are asserted via the API above.
  await page.getByRole("tab", { name: "Belege" }).first().click()
  await expect(page.getByText(/Verkn/).first()).toBeVisible({ timeout: 20_000 })
  await page.reload()
  await expect(page.getByText("Strukturvorlage").first()).toBeVisible({
    timeout: 20_000,
  })

  await page.goto("/")
  await page.getByText(/Produktionsanlagen \(Demo\)/).click()
  await expect(page).toHaveURL(/\/anforderungen/, { timeout: 20_000 })
  await expect(page.getByText(/rdervoraussetzungen/).first()).toBeVisible({
    timeout: 20_000,
  })
  // Blocked project: the blocker-aware footer ("… Blocker verhindern aktuell den
  // nächsten Schritt") is shown only when blockers exist.
  await expect(page.getByText(/verhinder/).first()).toBeVisible()
  await page.reload()
  await expect(page.getByText(/verhinder/).first()).toBeVisible({
    timeout: 20_000,
  })

  await page.goto("/")
  await expect(page.getByRole("button", { name: "Review freigeben" })).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Export erstellen" })).toHaveCount(0)
})
