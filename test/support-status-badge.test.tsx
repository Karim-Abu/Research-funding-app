// R6 Evidence-Statusleiter — Akzeptanzkriterium: location_found (Textstelle
// gefunden) darf NIE wie fachliche Verifikation wirken: kein grüner Stil,
// kein "belegt"/"bestätigt"/"verifiziert" im Label. Grün ist ausschliesslich
// supports_strongly.
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { SupportStatusBadge } from "@/components/status/support-status-badge"
import {
  SUPPORT_STATUS_LABELS,
  SUPPORT_STATUS_STYLES,
  supportStatusFromVerification,
  type SupportStatus,
} from "@/lib/evidence-ladder"

const GREEN = "status-fulfilled"
const FORBIDDEN_VERIFICATION_WORDS = /belegt|bestätigt|verifiziert/i

describe("SupportStatusBadge (R6-Statusleiter)", () => {
  it("location_found rendert nicht grün und nicht als 'belegt'", () => {
    const { container } = render(<SupportStatusBadge status="location_found" />)
    const badge = container.querySelector("span")
    expect(badge?.className ?? "").not.toContain(GREEN)
    expect(
      screen.getByText("Textstelle gefunden – fachliche Prüfung offen")
    ).toBeInTheDocument()
    expect(badge?.textContent ?? "").not.toMatch(FORBIDDEN_VERIFICATION_WORDS)
  })

  it("grün ist ausschliesslich supports_strongly", () => {
    const greenStatuses = (
      Object.keys(SUPPORT_STATUS_STYLES) as SupportStatus[]
    ).filter((status) => SUPPORT_STATUS_STYLES[status].includes(GREEN))
    expect(greenStatuses).toEqual(["supports_strongly"])
  })

  it("kein Label suggeriert Verifikation ausser den supports_-Stufen", () => {
    for (const [status, label] of Object.entries(SUPPORT_STATUS_LABELS)) {
      if (status.startsWith("supports_")) continue
      expect(label).not.toMatch(FORBIDDEN_VERIFICATION_WORDS)
    }
  })

  it("rendert alle sieben Stufen mit deutschem Label", () => {
    for (const status of Object.keys(SUPPORT_STATUS_LABELS) as SupportStatus[]) {
      const { unmount } = render(<SupportStatusBadge status={status} />)
      expect(screen.getByText(SUPPORT_STATUS_LABELS[status])).toBeInTheDocument()
      unmount()
    }
  })

  it("Anzeige-Fallback ohne Backend-Feld erreicht nie eine supports_-Stufe", () => {
    expect(supportStatusFromVerification("exact_verified")).toBe("location_found")
    expect(supportStatusFromVerification("human_verified")).toBe("location_found")
    expect(supportStatusFromVerification("rejected")).toBe("conflict_or_uncertain")
    expect(supportStatusFromVerification("unverified")).toBe(
      "human_review_required"
    )
  })
})
