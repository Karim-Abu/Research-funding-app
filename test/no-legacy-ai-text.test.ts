import { describe, it, expect } from "vitest"
import fs from "node:fs"
import path from "node:path"

// R4.2 — Grep-Guard: der generische Satz «… für diese Datenklasse oder Umgebung
// nicht verfügbar» darf ohne reason_code nicht mehr im Produktcode vorkommen.
// (docs/ und Kataloge sind bewusst ausgenommen — dort wird er als Alttext zitiert.)

const ROOT = process.cwd()
const SCAN_DIRS = ["lib", "components", "app", path.join("backend", "app")]
const EXTENSIONS = new Set([".ts", ".tsx", ".py"])
const SKIP_DIRS = new Set(["node_modules", "__pycache__", ".next"])
const LEGACY_TEXT = "für diese Datenklasse oder Umgebung nicht verfügbar"

function* walk(dir: string): Generator<string> {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue
      yield* walk(p)
    } else if (EXTENSIONS.has(path.extname(entry.name))) {
      yield p
    }
  }
}

describe("R4.2 — Alttext-Guard", () => {
  it("legacy generic AI-unavailable sentence is gone from product code", () => {
    const offenders: string[] = []
    for (const dir of SCAN_DIRS) {
      const abs = path.join(ROOT, dir)
      if (!fs.existsSync(abs)) continue
      for (const file of walk(abs)) {
        if (fs.readFileSync(file, "utf8").includes(LEGACY_TEXT)) {
          offenders.push(path.relative(ROOT, file))
        }
      }
    }
    expect(offenders).toEqual([])
  })
})
