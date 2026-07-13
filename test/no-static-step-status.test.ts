// Regressions-Guard (Workflow-Wahrheit): Die Seiten dürfen weder eigene
// statische Step-Arrays noch eine eigene Run-Auswahl («irgendein erster
// completed-Run») führen. Schrittstatus kommt aus lib/workflow.ts, die
// Run-ID aus der zentralen Ladder (lib/active-run.ts, useActiveRun).
// Muster analog test/no-legacy-ai-text.test.ts (Source-Scan in Vitest).

import { describe, expect, it } from "vitest"
import fs from "node:fs"
import path from "node:path"

const ROOT = process.cwd()

const PAGE_FILES = [
  "app/intake/page.tsx",
  "app/import/page.tsx",
  "app/quellen/page.tsx",
  "app/anforderungen/page.tsx",
  "app/editor/page.tsx",
  "app/review/page.tsx",
  "app/export/page.tsx",
  "app/portal-transfer/page.tsx",
  "components/import/import-review.tsx",
  "components/partner/partner-manager.tsx",
]

const FORBIDDEN: { name: string; pattern: RegExp }[] = [
  // Statische done/current-Arrays und Stepper-Props sind abgeschafft.
  { name: "stepStatus-Identifier", pattern: /\bstepStatus\b/ },
  { name: "currentStep-Prop", pattern: /currentStep=\{/ },
  // Run-Auswahl per «erster completed aus der Liste» ist verboten.
  { name: "find(status === completed)", pattern: /\.find\([^)]*"completed"/ },
  // Seiten listen Runs nicht mehr selbst — das macht der Provider.
  { name: "listProjectRuns-Import", pattern: /\blistProjectRuns\b/ },
]

describe("Workflow-Wahrheit — keine statischen Step-Arrays / Run-Eigenauswahl", () => {
  for (const file of PAGE_FILES) {
    it(`${file} nutzt den zentralen Workflow-/Run-Zustand`, () => {
      const source = fs.readFileSync(path.join(ROOT, file), "utf8")
      const offenders = FORBIDDEN.filter(({ pattern }) => pattern.test(source))
      expect(
        offenders.map((o) => o.name),
        `${file} enthält verbotene Muster`
      ).toEqual([])
    })
  }

  it("alle sechs Kernseiten existieren (Guard-Abdeckung bleibt vollständig)", () => {
    for (const file of PAGE_FILES) {
      expect(fs.existsSync(path.join(ROOT, file)), file).toBe(true)
    }
  })
})
