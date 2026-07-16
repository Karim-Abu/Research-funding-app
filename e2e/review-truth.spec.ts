import { test, expect } from "@playwright/test"
import {
  choosePublic,
  FIXTURE_PDF,
  getActiveProjectId,
  login,
  logout,
  mutFactory,
  waitForRunCompleted,
} from "./helpers"

// REVIEW-TRUTH-E2E: Statusanzeigen der Qualitätsprüfung sind fachlich ehrlich.
// 1. Der Bearbeitungs- und Prüfstand zeigt EXAKT die Zahlen des autoritativen
//    Check-Status-Views — «Nicht geprüft» ist ein eigenes Segment, nie grün.
// 2. Nach einer Feldänderung ist die Prüfung veraltet: 0/9 bestanden, alle
//    Bereiche «Nicht geprüft» — eine veraltete Prüfung erscheint nie als
//    bestanden.
// 3. Evidenz-Leiter: «Textstelle gefunden» (exact_verified ohne inhaltliches
//    Stützurteil) ist Abdeckung, keine fachliche Stützung — Badge-Zahlen im
//    UI entsprechen exakt den Support-Status-Werten der API.
//
// Ergänzt status-parity.spec.ts (Zahl «blockierende Aufgaben» über Dashboard/
// Anforderungen/Prüfung/Export) und die Backend-Pins in
// tests/test_z_check_status_view.py, test_evidence_support_status.py,
// test_review_truth.py. Fake-Provider, deterministisch, keine Web-Recherche.

interface CheckArea {
  area: string
  status: "not_run" | "passed" | "warning" | "failed"
}

interface AnchorDto {
  verification_status: string
  support_status: string | null
}

function progressAriaLabel(areas: CheckArea[]): string {
  const count = (status: CheckArea["status"]) =>
    areas.filter((a) => a.status === status).length
  return (
    `Bearbeitungs- und Prüfstand: ${count("passed")} von ${areas.length} ` +
    `Prüfbereichen bestanden, ${count("warning")} teilweise bestanden, ` +
    `${count("failed")} nicht bestanden, ` +
    `${count("not_run")} nicht geprüft.`
  )
}

test("Review-Truth: Prüfstatus und Evidenz-Leiter sind fachlich ehrlich", async ({
  page,
}) => {
  test.setTimeout(300_000)
  const title = `Review Truth ${Date.now()}`

  await test.step("1. Login und Projekt mit Analyse-Lauf", async () => {
    await login(page)
    await page.goto("/intake")
    await page.getByLabel(/Projekttitel/).fill(title)
    await page
      .getByRole("textbox", { name: /Projektidee/ })
      .fill("Synthetisches Projekt für den Review-Truth-Pfad.")
    await page.getByTestId("intake-file-input").setInputFiles(FIXTURE_PDF)
    await choosePublic(page)
    await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()
    await expect(page).toHaveURL(/\/import\?source=/, { timeout: 20_000 })
    await expect(page.getByTestId("import-review")).toBeVisible({ timeout: 60_000 })
  })

  const projectId = await getActiveProjectId(page)

  let runId = ""
  await test.step("2. Analyse mit Fake-Cloud-KI (ohne Web-Recherche)", async () => {
    await page.goto("/quellen")
    await page.getByRole("button", { name: "Analyse starten" }).click()
    const dialog = page.getByRole("dialog")
    // Fake-Modus: der Demo-Generator verlangt dieselbe ausdrückliche
    // Ein-Lauf-Bestätigung wie ein realer Modellaufruf. Der Schalter startet
    // je nach Capabilities-Ladezeitpunkt aus — idempotent einschalten.
    const kiSwitch = dialog.getByRole("switch", {
      name: /Demo-Vorschläge|KI-Unterstützung/,
    })
    if ((await kiSwitch.getAttribute("aria-checked")) !== "true") {
      await kiSwitch.click()
    }
    await dialog
      .getByRole("checkbox", { name: "Demo-Generator für diesen Durchlauf aktivieren" })
      .click()
    await dialog.getByRole("button", { name: "Analyse starten" }).click()
    runId = await waitForRunCompleted(page, projectId)
  })

  await test.step("3. Prüfstand zeigt exakt die autoritativen Zahlen", async () => {
    const checkStatus = await (
      await page.request.get(`/api/runs/${runId}/review/check-status`)
    ).json()
    const areas = checkStatus.areas as CheckArea[]
    expect(areas).toHaveLength(9)

    await page.goto("/review")
    const card = page.getByTestId("review-progress-card")
    await expect(card).toBeVisible({ timeout: 20_000 })
    // Der Ring trägt die vier Zahlen als einen barrierefreien Satz — er muss
    // exakt dem Check-Status-View entsprechen (keine eigene Frontend-Logik).
    await expect(
      card.getByRole("img", { name: progressAriaLabel(areas) })
    ).toBeVisible()
  })

  await test.step("4. Evidenz-Leiter: Textstelle gefunden ≠ inhaltlich gestützt", async () => {
    const anchors = (await (
      await page.request.get(`/api/runs/${runId}/evidence`)
    ).json()) as AnchorDto[]
    expect(anchors.length).toBeGreaterThan(0)

    const effective = (anchor: AnchorDto): string =>
      anchor.support_status ??
      (anchor.verification_status === "exact_verified"
        ? "location_found"
        : "human_review_required")
    const locationFound = anchors.filter(
      (a) => effective(a) === "location_found"
    ).length
    const stronglySupported = anchors.filter(
      (a) => effective(a) === "supports_strongly"
    ).length
    // Der Kernfall dieses Tests: mindestens ein Anker ist exakt verifiziert,
    // aber (noch) ohne inhaltliches Stützurteil.
    expect(locationFound).toBeGreaterThan(0)

    await page.goto("/anforderungen?tab=evidenz")
    // Der erklärende Hinweis zur Leiter ist sichtbar (Coverage ≠ Correctness).
    await expect(
      page.getByText(/«Textstelle gefunden» heisst nur/)
    ).toBeVisible({ timeout: 20_000 })
    const items = page.getByRole("listitem")
    await expect(
      items.getByText("Textstelle gefunden – fachliche Prüfung offen")
    ).toHaveCount(locationFound)
    // «Stark gestützt» (grün) erscheint NIE für einen Anker ohne Stützurteil.
    await expect(items.getByText("Stark gestützt", { exact: true })).toHaveCount(
      stronglySupported
    )
  })

  await test.step("5. Veraltete Prüfung erscheint nie als bestanden", async () => {
    const mut = await mutFactory(page)
    const draft = await (
      await page.request.get(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT`)
    ).json()
    await page.request.patch(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT`, {
      headers: mut(),
      data: {
        base_version_id: draft.current_version.draft_version_id,
        text: "Geänderter Abstract — die Prüfung ist jetzt veraltet.",
      },
    })

    const stale = await (
      await page.request.get(`/api/runs/${runId}/review/check-status`)
    ).json()
    expect(stale.stale).toBe(true)
    const areas = stale.areas as CheckArea[]
    // Kerninvariante: nach einer Änderung ist KEIN Bereich mehr «Bestanden» —
    // offene Findings bleiben ehrlich failed/warning, alles Übrige not_run.
    expect(areas.every((a) => a.status !== "passed")).toBe(true)
    expect(areas.some((a) => a.status === "not_run")).toBe(true)

    await page.goto("/review")
    const card = page.getByTestId("review-progress-card")
    await expect(card).toBeVisible({ timeout: 20_000 })
    await expect(card.getByText("Stand veraltet")).toBeVisible()
    // 0 von 9 bestanden — eine veraltete Prüfung ist nie stillschweigend grün.
    await expect(
      card.getByRole("img", { name: progressAriaLabel(areas) })
    ).toBeVisible()
  })

  await test.step("6. Abmelden", async () => {
    await logout(page)
  })
})
