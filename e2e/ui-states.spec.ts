import { test, expect, type Page } from "@playwright/test"
import {
  approveBriefViaApi,
  choosePublic,
  getActiveProjectId,
  login,
  mutFactory,
  waitOp,
  type Mut,
} from "./helpers"

// UI-Zustände (Aufgabe 4/5): Modalhöhe, sticky Footer und Tastaturbedienung des
// Analyse-Dialogs sowie das Verhalten eines langen 25'000-Zeichen-Feldes
// (Limit-Warnung + deaktiviertes Speichern). Deterministisch, Fake-Provider.
const PUBLIC_CLASSIFICATION = {
  sensitivity: "public",
  origin: "synthetic",
  processing_mode: "deterministic_only",
  web_research_mode: "off",
  nda_applies: false,
}
const SOLUTION = "SOL.INNOVATION_SOLUTION.EDITOR"

async function createPublicProject(page: Page, mut: Mut, title: string): Promise<string> {
  const projectId = (
    await (
      await page.request.post("/api/projects", {
        headers: mut(),
        data: {
          title,
          description: "UI-State-Testprojekt.",
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
      text: "Synthetischer öffentlicher Projektinhalt für den UI-State-Test.",
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

test("Analyse-Dialog: Höhe im Viewport, sichtbarer Footer, Escape schliesst", async ({
  page,
}) => {
  await login(page)
  // Projekt über das echte Intake anlegen (setzt den Intake-Zustand, der die
  // «Analyse starten»-Aktion freischaltet).
  await page.goto("/intake")
  await page.getByLabel(/Projekttitel/).fill(`UI Dialog ${Date.now()}`)
  await page
    .getByRole("textbox", { name: /Projektidee/ })
    .fill("Synthetisches Demo-Projekt für den Dialog-Layout-Test.")
  await choosePublic(page)
  await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()
  await expect(page).toHaveURL(/\/quellen/, { timeout: 20_000 })

  // Query-Planung setzt seit dem Brief-Gate einen freigegebenen public-safe
  // Recherchebrief voraus (API-Setup; HITL-UI-Variante im technischen E2E).
  const mut = await mutFactory(page)
  await approveBriefViaApi(page.request, mut, await getActiveProjectId(page))

  await page.getByRole("button", { name: "Analyse starten" }).click()
  const dialog = page.getByRole("dialog")
  await expect(dialog).toBeVisible({ timeout: 20_000 })

  const viewport = page.viewportSize()!

  // Modalhöhe bleibt im Viewport (max-h-[90dvh]) — kein Überlaufen nach unten.
  const dialogBox = await dialog.boundingBox()
  expect(dialogBox).not.toBeNull()
  expect(dialogBox!.height).toBeLessThanOrEqual(viewport.height + 1)

  // Web-Recherche einschalten macht den Inhalt länger (Query-Freigabeliste).
  await dialog.getByRole("switch", { name: /Öffentliche Webrecherche/ }).click()
  await expect(dialog.getByTestId("query-approval-list")).toBeVisible({ timeout: 20_000 })

  // Sticky Footer: der primäre Button bleibt sichtbar und vollständig im Viewport,
  // auch bei langem Dialoginhalt.
  const startButton = dialog.getByRole("button", { name: "Analyse starten" })
  await expect(startButton).toBeVisible()
  const btnBox = await startButton.boundingBox()
  expect(btnBox).not.toBeNull()
  expect(btnBox!.y + btnBox!.height).toBeLessThanOrEqual(viewport.height + 1)

  // Tastaturbedienung: Escape schliesst den Dialog.
  await page.keyboard.press("Escape")
  await expect(dialog).toBeHidden({ timeout: 20_000 })
})

test("Langes 25'000-Zeichen-Feld: Limit-Warnung und deaktiviertes Speichern", async ({
  page,
}) => {
  test.setTimeout(120_000)
  await login(page)
  const mut = await mutFactory(page)
  const projectId = await createPublicProject(page, mut, `UI Limit ${Date.now()}`)
  const runId = await completeDeterministicRun(page, mut, projectId)

  // Feld nahe an das 25'000-Zeichen-Limit füllen (unter dem Limit, wird akzeptiert).
  const field = await (
    await page.request.get(`/api/runs/${runId}/fields/${SOLUTION}`)
  ).json()
  const marker = "GOLDENPATHMARKER"
  const longText = marker + "a".repeat(24_995 - marker.length)
  const patched = await page.request.patch(`/api/runs/${runId}/fields/${SOLUTION}`, {
    headers: mut(),
    data: { base_version_id: field.current_version.draft_version_id, text: longText },
  })
  expect(patched.status()).toBe(200)

  await page.evaluate((id) => sessionStorage.setItem("rf_active_project_id", id), projectId)
  await page.goto(`/editor?field=${SOLUTION}`)

  // Das lange Feld rendert ohne Layout-Bruch; der Zähler zeigt das Limit.
  const editor = page.getByLabel(/^Entwurf /)
  await expect(editor).toContainText(marker, { timeout: 20_000 })
  // Der Zähler zeigt das Limit (de-CH-Tausendertrennung: 25'000).
  await expect(page.getByText(/25.?000 Zeichen/).first()).toBeVisible()

  // Über das Limit tippen → klare Warnung + Speichern deaktiviert.
  await editor.click()
  await page.keyboard.press("ControlOrMeta+End")
  await editor.pressSequentially("bbbbbbbbbbbbbbb")
  await expect(
    page.getByText(/überschreitet das Innolink-Zeichenlimit/)
  ).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole("button", { name: "Speichern" })).toBeDisabled()
})
