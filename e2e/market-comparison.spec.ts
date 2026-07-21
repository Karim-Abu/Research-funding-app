import { test, expect, type APIRequestContext, type Page } from "@playwright/test"

type Mut = () => Record<string, string>

// M9I-B market/competitor comparison smoke (fake provider). Requires the backend started
// with WEB_RESEARCH_ENABLED=true, WEB_RESEARCH_FAKE_PROVIDER=true, AGENT_FAKE_PROVIDER=true.
// EHRLICHER Fake-Modus: Demo-Recherche liefert keine echten Webquellen — der
// Vergleich wird bewusst LEER abgeschlossen (Evidenzlücke ausgewiesen), nie
// aus Fake-Inhalten fabriziert. Source-backed Items sind ein Live-Thema
// (Ebene D / Supervised live E2E).
const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const CLASSIFICATION = {
  sensitivity: "public", origin: "synthetic", processing_mode: "cloud_assisted",
  web_research_mode: "validated_public", nda_applies: false,
}

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

async function waitForOperation(request: APIRequestContext, opId: string): Promise<string> {
  let status = ""
  for (let i = 0; i < 60; i++) {
    status = (await (await request.get(`/api/operations/${opId}`)).json()).status
    if (["succeeded", "failed", "cancelled"].includes(status)) break
    await new Promise((r) => setTimeout(r, 500))
  }
  return status
}

async function login(page: Page): Promise<Mut> {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })
  const csrf = (await (await page.request.get("/api/session")).json()).csrf_token as string
  return () => ({
    "X-CSRF-Token": csrf, Origin: ORIGIN, "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })
}

async function createProject(request: APIRequestContext, mut: Mut): Promise<string> {
  return (await (await request.post("/api/projects", {
    headers: mut(),
    data: {
      title: "E2E Market", description: "Market comparison smoke.",
      funding_instrument_profile_id:
        "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })).json()).project_id
}

test("market comparison: fake mode completes honestly empty with gap note", async ({ page }) => {
  const mut = await login(page)
  const projectId = await createProject(page.request, mut)

  // Generate the comparison (fake web mode).
  const accepted = await (await page.request.post(
    `/api/projects/${projectId}/market-comparisons`, { headers: mut() })).json()
  expect(await waitForOperation(page.request, accepted.operation_id)).toBe("succeeded")

  const view = await (await page.request.get(
    `/api/market-comparisons/${accepted.resource_id}`)).json()
  // Ehrlicher Leerzustand: bereit zur Prüfung, aber 0 Items + klare Lücke.
  // Ohne zwei gepruefte externe Quellen ist kein Vergleich pruefbereit.
  expect(view.status).toBe("insufficient_external_evidence")
  expect(view.item_count ?? (view.items ?? []).length).toBe(0)
  expect(view.warnings).toContain("insufficient_external_evidence")
  expect(JSON.stringify(view.research_gaps)).toContain(
    "Demo-Recherche enth\u00e4lt keine echten Webquellen"
  )

  // No drafts were created by the comparison (no automatic draft mutation).
  const sources = await (await page.request.get(`/api/projects/${projectId}/sources`)).json()
  expect(Array.isArray(sources)).toBe(true)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})

test("market comparison UI: Quellen section shows the honest empty state", async ({ page }) => {
  const mut = await login(page)
  const projectId = await createProject(page.request, mut)

  await page.evaluate((id) => sessionStorage.setItem("rf_active_project_id", id), projectId)
  await page.goto("/quellen")

  const section = page.getByTestId("market-comparison-section")
  await expect(section).toBeVisible({ timeout: 20_000 })
  await expect(section).toContainText("Markt- und Konkurrenzvergleich")

  // Quellen-Gate: ohne eine live abgerufene, importierte und inhaltlich
  // positiv geprüfte Quelle ist «Vergleich erstellen» sichtbar deaktiviert —
  // mit konkretem Grund statt eines leeren Demo-Vergleichs (CLAUDEX:
  // deaktivierte Buttons erklären sich).
  await expect(
    section.getByRole("button", { name: "Vergleich erstellen" })
  ).toBeDisabled()
  await expect(
    section.getByTestId("market-comparison-disabled-reason")
  ).toContainText(
    "Noch keine live abgerufene, importierte und inhaltlich positiv geprüfte Quelle"
  )
  await expect(page.getByTestId("market-comparison-table")).toHaveCount(0)
  // No provider/model branding anywhere on the page.
  await expect(page.locator("body")).not.toContainText(/firecrawl|anthropic|haiku/i)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
