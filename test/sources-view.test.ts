// RUN 4A — Zweck-Gruppierung der Quellen: ausschliesslich kanonische
// Metadaten (Primärantrag + data_classification.origin), nie Dateinamen.
import { describe, it, expect } from "vitest"

import {
  PRIMARY_APPLICATION_HINTS,
  SOURCE_GROUP_LABELS,
  SOURCE_GROUP_ORDER,
  sourceGroupOf,
} from "@/lib/sources-view"
import type { DataClassification, Origin } from "@/lib/data-classification"

function classification(origin: Origin): DataClassification {
  return {
    sensitivity: "public",
    origin,
    processing_mode: "deterministic_only",
    web_research_mode: "off",
    nda_applies: false,
  }
}

describe("sourceGroupOf", () => {
  it("ordnet die Primärantragsquelle der Gruppe «Primärer Innolink-Antrag» zu", () => {
    expect(
      sourceGroupOf(
        { source_id: "s-1", data_classification: classification("real_project") },
        "s-1"
      )
    ).toBe("primary_application")
  })

  it("ordnet public_source-Quellen der öffentlichen Recherche zu — auch bei projektähnlichem Dateinamen", () => {
    // Der Name spielt keine Rolle: nur origin entscheidet.
    expect(
      sourceGroupOf(
        {
          source_id: "s-2",
          data_classification: classification("public_source"),
        },
        "s-1"
      )
    ).toBe("public_research")
  })

  it("alle übrigen Origins sind Projektunterlagen", () => {
    for (const origin of ["real_project", "synthetic", "anonymized"] as const) {
      expect(
        sourceGroupOf(
          { source_id: "s-3", data_classification: classification(origin) },
          "s-1"
        )
      ).toBe("project_documents")
    }
  })

  it("ohne festgelegten Primärantrag gibt es keine Primärgruppe", () => {
    expect(
      sourceGroupOf(
        { source_id: "s-1", data_classification: classification("real_project") },
        null
      )
    ).toBe("project_documents")
  })
})

describe("Gruppen-Katalog", () => {
  it("führt genau drei Gruppen in fester Reihenfolge mit Nutzersprache", () => {
    expect(SOURCE_GROUP_ORDER).toEqual([
      "primary_application",
      "project_documents",
      "public_research",
    ])
    expect(SOURCE_GROUP_LABELS.primary_application).toBe(
      "Primärer Innolink-Antrag"
    )
    expect(SOURCE_GROUP_LABELS.project_documents).toBe("Projektunterlagen")
    expect(SOURCE_GROUP_LABELS.public_research).toBe("Öffentliche Recherche")
  })

  it("Hinweise für fehlenden Primärantrag sind nutzerfreundlich (kein Technik-Wording)", () => {
    for (const hint of Object.values(PRIMARY_APPLICATION_HINTS)) {
      expect(hint).not.toMatch(/source_id|primary_application|null|undefined/)
    }
  })
})
