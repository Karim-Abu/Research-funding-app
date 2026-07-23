// UX-Refactor (Analyse-Sheet, Composite-Fokusansicht, Stepper) — Viewport-
// Abnahme bei 1366×768 und 1920×1080: Start-/Übernehmen-Aktionen bleiben ohne
// Seitenscroll erreichbar, das 25k-Feld ist abschnittsweise bedienbar, der
// Stepper folgt Artefakten. Deterministisch, Fake-Provider. Voraussetzung:
// Migration + Demo-Seed + beide Server (Backend :8000, Frontend :3000).
import { expect, test, type Page } from "@playwright/test"

import { choosePublic, login, mutFactory, waitOp, type Mut } from "./helpers"

const PUBLIC_CLASSIFICATION = {
  sensitivity: "public",
  origin: "synthetic",
  processing_mode: "deterministic_only",
  web_research_mode: "off",
  nda_applies: false,
}
const VC_FIELD = "VC.BUSINESS_TARGETS_MODEL.EDITOR"

async function createPublicProject(page: Page, mut: Mut, title: string): Promise<string> {
  const projectId = (
    await (
      await page.request.post("/api/projects", {
        headers: mut(),
        data: {
          title,
          description: "UX-Refactor-Testprojekt.",
          funding_instrument_profile_id:
            "innosuisse_innovation_project_with_implementation_partner",
          data_classification: PUBLIC_CLASSIFICATION,
        },
      })
    ).json()
  ).project_id as string
  await page.request.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(),
    data: {
      name: "Notiz",
      text: "Synthetischer öffentlicher Projektinhalt für den UX-Refactor-Test.",
      data_classification: PUBLIC_CLASSIFICATION,
    },
  })
  return projectId
}

async function completeDeterministicRun(
  page: Page,
  mut: Mut,
  projectId: string
): Promise<string> {
  const accepted = await (
    await page.request.post(`/api/projects/${projectId}/runs`, {
      headers: mut(),
      data: {
        settings: {
          processing_mode: "deterministic_only",
          max_cost_chf: 0,
          max_llm_calls: 0,
          max_web_calls: 0,
        },
      },
    })
  ).json()
  expect(await waitOp(page.request, accepted.operation_id)).toBe("succeeded")
  return accepted.resource_id as string
}

async function assertNoPageScroll(page: Page): Promise<void> {
  const { scrollY, scrollWidth, innerWidth } = await page.evaluate(() => ({
    scrollY: window.scrollY,
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }))
  expect(scrollY).toBe(0)
  // Kein horizontaler Scroll der Seite (Toleranz für Scrollbar-Rundung).
  expect(scrollWidth).toBeLessThanOrEqual(innerWidth + 1)
}

async function openAnalyseSheetViaIntake(page: Page): Promise<void> {
  await login(page)
  // Projekt über das echte Intake anlegen (schaltet «Analyse starten» frei).
  await page.goto("/intake")
  await page.getByLabel(/Projekttitel/).fill(`UX Refactor ${Date.now()}`)
  await page
    .getByRole("textbox", { name: /Projektidee/ })
    .fill("Synthetisches Demo-Projekt für den UX-Refactor-Viewport-Test.")
  await choosePublic(page)
  await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()
  await expect(page).toHaveURL(/\/quellen/, { timeout: 20_000 })
  await page.getByRole("button", { name: "Analyse starten" }).click()
}

for (const viewport of [
  { width: 1366, height: 768 },
  { width: 1920, height: 1080 },
]) {
  test.describe(`Analyse-Konfiguration @ ${viewport.width}×${viewport.height}`, () => {
    test.use({ viewport })

    test("Sheet passt in den Viewport; Start bleibt ohne Seitenscroll erreichbar", async ({
      page,
    }) => {
      test.setTimeout(120_000)
      await openAnalyseSheetViaIntake(page)

      const sheet = page.locator('[data-slot="sheet-content"]')
      await expect(sheet).toBeVisible({ timeout: 20_000 })
      // Breite Konfigurationsansicht (≥880 px), Höhe im Viewport.
      const sheetBox = await sheet.boundingBox()
      expect(sheetBox!.width).toBeGreaterThanOrEqual(879)
      expect(sheetBox!.height).toBeLessThanOrEqual(viewport.height + 1)

      const start = page
        .locator('[data-slot="sheet-footer"]')
        .getByRole("button", { name: "Analyse starten" })
      await expect(start).toBeVisible()
      const btnBox = await start.boundingBox()
      expect(btnBox!.y + btnBox!.height).toBeLessThanOrEqual(viewport.height + 1)
      await assertNoPageScroll(page)

      // Ehrliche Phasenvorschau statt Schätzwerte — seit 2026-07-23 eingeklappt
      // (progressive Disclosure): erst der Trigger zeigt die Liste.
      await expect(
        page.getByRole("button", { name: "Erwartete Phasen" })
      ).toBeVisible()
      await page.getByRole("button", { name: "Erwartete Phasen" }).click()
      await expect(page.getByTestId("expected-phases")).toBeVisible()
    })
  })
}

test.describe("Composite-Fokusansicht @ 1366×768", () => {
  test.use({ viewport: { width: 1366, height: 768 } })

  test("3.x separat lesen/bearbeiten; Wechsel verliert keine Eingabe", async ({
    page,
  }) => {
    test.setTimeout(120_000)
    await login(page)
    const mut = await mutFactory(page)
    const projectId = await createPublicProject(page, mut, `UX Fokus ${Date.now()}`)
    await completeDeterministicRun(page, mut, projectId)
    await page.evaluate(
      (id) => sessionStorage.setItem("rf_active_project_id", id),
      projectId
    )
    await page.goto(`/editor?field=${VC_FIELD}`)

    const nav = page.getByRole("navigation", { name: "Unterabschnitte" })
    await expect(nav).toBeVisible({ timeout: 20_000 })

    // Fokusansicht: Portalfrage-Karte sichtbar, nicht editierbar.
    await expect(page.getByTestId("subsection-question")).toBeVisible()
    await expect(page.getByText("Portalfrage – nicht editierbar")).toBeVisible()

    // In 3.2 wechseln und tippen (Tiptap-Editor).
    await nav.getByRole("button", { name: /^3\.2/ }).click()
    await expect(page.getByTestId("subsection-count")).toContainText("3.2")
    const editor = page.locator('[contenteditable="true"]').first()
    await editor.click()
    await page.keyboard.type(" E2E-ERGÄNZUNG.")

    // Abschnittswechsel hin und zurück — Eingabe bleibt (Single-Buffer).
    await nav.getByRole("button", { name: /^3\.1/ }).click()
    await expect(page.getByTestId("subsection-count")).toContainText("3.1")
    await nav.getByRole("button", { name: /^3\.2/ }).click()
    await expect(editor).toContainText("E2E-ERGÄNZUNG.")

    // Gesamtlimit bleibt neben dem Segmentzähler sichtbar.
    await expect(page.getByText(/15\s*000|15000/).first()).toBeVisible()
    await assertNoPageScroll(page)
  })
})

test.describe("Stepper folgt Artefakten @ 1366×768", () => {
  test.use({ viewport: { width: 1366, height: 768 } })

  test("Entwurf zeigt Statustext aus Artefakten; kein Haken ohne Freigabe", async ({
    page,
  }) => {
    await login(page)
    // Demo-Projekt A hat Nutzer-Edits ⇒ Entwurf «In Bearbeitung» (artefaktbasiert).
    await page.goto("/editor")
    const stepper = page.getByRole("navigation", { name: "Arbeitsschritte" }).first()
    await expect(stepper).toBeVisible({ timeout: 20_000 })
    // Der Statustext steht im aria-label («Schritt 4: … — Status»).
    const entwurf = stepper.locator('[aria-label*="Antragsentwurf"]').first()
    await expect(entwurf).toHaveAttribute(
      "aria-label",
      /Antragsentwurf — (In Bearbeitung|Nicht begonnen)/
    )
    // Kein Häkchen, solange keine gültige Freigabe existiert.
    await expect(entwurf.locator("svg.lucide-check")).toHaveCount(0)
  })
})
