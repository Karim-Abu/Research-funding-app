import { test, expect, type APIRequestContext } from "@playwright/test"

// Milestone 8.1 Innolink transfer view — frontend-only copy assistant (no export,
// no backend change, no portal automation). Clipboard permissions are granted so
// the test can read back what was copied.
test.use({ permissions: ["clipboard-read", "clipboard-write"] })

const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const CLASSIFICATION = {
  sensitivity: "public",
  origin: "synthetic",
  processing_mode: "deterministic_only",
  web_research_mode: "off",
  nda_applies: false,
}
const SOURCE_TEXT =
  "Der Umsetzungspartner ist in der Schweiz wertschöpfend tätig. " +
  "Ein beitragsberechtigter Schweizer Forschungspartner ist eingebunden."
const ABSTRACT = "INTRO.APP.ABSTRACT"
const COMPOSITE = "SOL.INNOVATION_SOLUTION.EDITOR"

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

// The product copies the exact field text; the OS/headless clipboard round-trip
// may re-frame line endings / trailing whitespace, so compare on that basis.
function normalize(s: string): string {
  return s
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((l) => l.replace(/[ \t]+$/, ""))
    .join("\n")
    .trim()
}

async function completeRun(api: APIRequestContext, mut: () => Record<string, string>) {
  const projectId = (await (await api.post("/api/projects", {
    headers: mut(),
    data: {
      title: "M8.1 Transfer",
      description: "Innolink transfer e2e.",
      funding_instrument_profile_id:
        "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })).json()).project_id as string
  await api.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(),
    data: { name: "Quelle", text: SOURCE_TEXT, data_classification: CLASSIFICATION },
  })
  for (const partner of [
    { name: "Industrie AG", partner_type: "implementation_partner", country: "CH", swiss_value_creation: true },
    { name: "ETH", partner_type: "research_partner", country: "CH", research_partner_eligibility_status: "eligible" },
  ]) {
    await api.post(`/api/projects/${projectId}/partners`, { headers: mut(), data: partner })
  }
  const accepted = await (await api.post(`/api/projects/${projectId}/runs`, {
    headers: mut(),
    data: { settings: { processing_mode: "deterministic_only", max_cost_chf: 0, max_llm_calls: 0, max_web_calls: 0 } },
  })).json()
  let status = ""
  for (let i = 0; i < 50; i++) {
    status = (await (await api.get(`/api/operations/${accepted.operation_id}`)).json()).status
    if (["succeeded", "failed", "cancelled"].includes(status)) break
    await new Promise((r) => setTimeout(r, 300))
  }
  expect(status).toBe("succeeded")
  return { projectId, runId: accepted.resource_id as string }
}

async function copyCard(page: import("@playwright/test").Page, fieldName: string) {
  const card = page.locator("article", {
    has: page.getByRole("heading", { name: fieldName, exact: true }),
  })
  // Copy-ready fields lead with "Text kopieren"; open fields require the
  // deliberate "Trotzdem kopieren…" path (M10.2 / F5).
  const plainCopy = card.getByRole("button", { name: "Text kopieren" })
  if (await plainCopy.isVisible().catch(() => false)) {
    await plainCopy.click()
  } else {
    await card.getByRole("button", { name: "Trotzdem kopieren…" }).click()
  }
  const confirm = card.getByRole("button", { name: "Trotzdem kopieren", exact: true })
  if (await confirm.isVisible().catch(() => false)) await confirm.click()
  await expect(card.getByText(/Kopiert am/)).toBeVisible()
}

test("M8.1 Innolink transfer: field order, copy-only-content, warnings, coverage", async ({
  page,
}) => {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  const api = page.request
  const csrf = (await (await api.get("/api/session")).json()).csrf_token as string
  const mut = () => ({
    "X-CSRF-Token": csrf, Origin: ORIGIN, "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })

  const { projectId, runId } = await completeRun(api, mut)
  const fields = (await (await api.get(`/api/runs/${runId}/fields`)).json()) as Array<{
    field_id: string
    field_name: string
    current_version: { text: string }
  }>
  const abstract = fields.find((f) => f.field_id === ABSTRACT)!
  const composite = fields.find((f) => f.field_id === COMPOSITE)!

  // Open via the Export Center → "Innolink-Kopieransicht" tab (renders inline).
  await page.evaluate((pid) => sessionStorage.setItem("rf_active_project_id", pid), projectId)
  await page.goto("/export")
  await page.getByRole("tab", { name: "Innolink-Kopieransicht" }).click()
  // The transfer view renders inline (embedded; the page h1 is omitted) — the
  // coverage panel confirms it loaded.
  await expect(
    page.getByRole("heading", { name: "Abdeckung der Übernahmeansicht" })
  ).toBeVisible({ timeout: 20_000 })

  // Section groups in canonical order.
  for (const section of ["Einleitung", "Wertschöpfung", "Lösung & Innovation", "Projektplan"]) {
    await expect(page.getByRole("heading", { name: section, exact: true })).toBeVisible()
  }

  // Copy the Abstract (a template placeholder → compact warning badge on the
  // card; the full sentence appears in the shared banner + confirm step).
  await expect(
    page
      .locator("article", { has: page.getByRole("heading", { name: abstract.field_name }) })
      .getByText("Offene Angaben"),
  ).toBeVisible()
  await copyCard(page, abstract.field_name)
  expect(normalize(await page.evaluate(() => navigator.clipboard.readText()))).toBe(
    normalize(abstract.current_version.text),
  )

  // Copy a composite field → clipboard holds only that field's full text.
  await copyCard(page, composite.field_name)
  expect(normalize(await page.evaluate(() => navigator.clipboard.readText()))).toBe(
    normalize(composite.current_version.text),
  )

  // Coverage panel marks structured areas as manual Innolink entry.
  await expect(page.getByText(/Arbeitspakete \(Work Packages\)/)).toBeVisible()
  await expect(page.getByText(/Budget- und Finanzierungsplan/)).toBeVisible()
  await expect(
    page.getByText(/müssen weiterhin direkt in\s+Innolink erfasst werden/),
  ).toBeVisible()

  await api.delete("/api/session", { headers: { "X-CSRF-Token": csrf, Origin: ORIGIN } })
})
