import path from "node:path"
import { expect, type APIRequestContext, type Page } from "@playwright/test"

// Gemeinsame E2E-Helfer für die neuen Golden-Path-/UI-State-Specs. Extrahiert die
// bereits in mehreren Specs bewährten Muster (Login, CSRF-Header, Operation-Poll,
// Klassifikationswahl, Run-Abschluss) an einer Stelle. Bestehende Specs bleiben
// unverändert und importieren diese Datei NICHT.
export type Mut = () => Record<string, string>

export const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
export const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
export const ORIGIN = "http://localhost:3000"

// Synthetisches Innolink-Fixture (Projekt «SmartGrid Optimizer»); deterministisch,
// 8/8 Feld-Mapping. Kein echtes Antragsdokument (Testdaten-Policy E-12).
export const FIXTURE_PDF = path.join(
  __dirname, "..", "spike", "fixtures", "innolink_sample.pdf"
)

export function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

/** Login über die echte Anmeldemaske; danach steht die Session (Cookie + CSRF). */
export async function login(page: Page): Promise<void> {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })
}

/** Header-Fabrik für schreibende API-Aufrufe (nur zum Vor-/Nachbereiten im Test). */
export async function mutFactory(page: Page): Promise<Mut> {
  const csrf = (await (await page.request.get("/api/session")).json())
    .csrf_token as string
  return () => ({
    "X-CSRF-Token": csrf,
    Origin: ORIGIN,
    "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })
}

/** Wartet auf den terminalen Status einer Operation (Poll gegen die BFF-API). */
export async function waitOp(
  request: APIRequestContext,
  opId: string
): Promise<string> {
  let status = ""
  for (let i = 0; i < 60; i++) {
    status = (await (await request.get(`/api/operations/${opId}`)).json()).status
    if (["succeeded", "failed", "cancelled"].includes(status)) break
    await new Promise((r) => setTimeout(r, 500))
  }
  return status
}

/** Öffentliche Demo-Daten über den kompakten «Ändern»-Dialog wählen. */
export async function choosePublic(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Ändern" }).click()
  const dialog = page.getByRole("dialog")
  await dialog.getByText("Öffentlich", { exact: true }).click()
  await dialog.getByRole("button", { name: "Fertig" }).click()
  await expect(dialog).toBeHidden()
}

/** Aktive Projekt-ID aus dem Session-Storage (nach dem Intake gesetzt). */
export async function getActiveProjectId(page: Page): Promise<string> {
  const id = await page.evaluate(() =>
    window.sessionStorage.getItem("rf_active_project_id")
  )
  expect(id).toBeTruthy()
  return id as string
}

/**
 * Wartet auf den frisch gestarteten Analyse-Lauf: das Banner erscheint
 * optimistisch VOR der POST-/runs-Antwort, daher wird die Run-Liste gepollt,
 * bis der Lauf angelegt und terminal (completed) ist.
 */
export async function waitForRunCompleted(
  page: Page,
  projectId: string
): Promise<string> {
  await expect(
    page
      .getByText("Analyse läuft")
      .or(page.getByText(/Analyse (teilweise )?abgeschlossen/))
      .first()
  ).toBeVisible({ timeout: 20_000 })
  let runId = ""
  for (let i = 0; i < 60; i++) {
    const runs = await (
      await page.request.get(`/api/projects/${projectId}/runs`)
    ).json()
    if (runs.items?.length) {
      runId = runs.items[0].run_id as string
      break
    }
    await page.waitForTimeout(500)
  }
  expect(runId).toBeTruthy()
  let status = ""
  for (let i = 0; i < 60; i++) {
    status = (await (await page.request.get(`/api/runs/${runId}`)).json()).status
    if (["completed", "failed", "stopped", "cancelled"].includes(status)) break
    await page.waitForTimeout(500)
  }
  expect(status).toBe("completed")
  return runId
}

/**
 * Legt per API einen public-safe Recherchebrief an und gibt ihn frei.
 * Seit dem Brief-Gate entstehen Recherche-Queries NUR aus einem menschlich
 * freigegebenen Brief — Tests, die Queries planen/ausführen, brauchen dieses
 * Setup (die HITL-UI-Variante zeigt der technische E2E).
 */
export async function approveBriefViaApi(
  request: APIRequestContext,
  mut: Mut,
  projectId: string,
  modules: string[] = ["market_growth"]
): Promise<string> {
  const briefResponse = await request.put(
    `/api/projects/${projectId}/research-brief`,
    {
      headers: mut(),
      data: {
        application_domain: "Energiemanagement",
        technology_class: "Prognosesoftware",
        target_customer_segments: ["Verteilnetzbetreiber"],
        region: "Schweiz",
        competence_needs: ["Energiedatenanalyse"],
        modules,
      },
    }
  )
  expect(briefResponse.ok()).toBeTruthy()
  const brief = await briefResponse.json()
  const approved = await request.post(
    `/api/research-briefs/${encodeURIComponent(brief.research_brief_id)}/approve`,
    { headers: mut() }
  )
  expect(approved.ok()).toBeTruthy()
  return brief.research_brief_id as string
}

/** Wartet, bis die Qualitätsprüfung eines Laufs keine erneute Prüfung mehr fordert. */
export async function waitForRecheckCleared(
  request: APIRequestContext,
  runId: string
): Promise<void> {
  let cleared = false
  for (let i = 0; i < 60; i++) {
    const pkg = await (await request.get(`/api/runs/${runId}/review`)).json()
    if (pkg.recheck_required === false) {
      cleared = true
      break
    }
    await new Promise((r) => setTimeout(r, 500))
  }
  expect(cleared).toBe(true)
}

/** Abmelden über das Benutzer-Menü in der Topbar. */
export async function logout(page: Page): Promise<void> {
  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
}
