// Echter Text-Vergleich für den Vorschlagsvergleich (C2) — pures Rechenmodul,
// keine Dependency (Nutzerentscheid E1): Satz-LCS klassifiziert
// beibehalten/entfernt/hinzugefügt; einander gegenüberstehende
// Entfernt/Neu-Paare mit ausreichender Wort-Überlappung gelten als
// «umformuliert» und erhalten einen wortweisen Inner-Diff. Die Segmente
// tragen Offsets in den Ausgangstext, damit `applySegments` einzelne
// Änderungen übernehmen kann, ohne unberührte Passagen umzuformatieren.
// Kein Netzwerk, keine UI-Strings — Labels/Farben liegen bei der Komponente.

export type DiffKind = "beibehalten" | "entfernt" | "hinzugefuegt" | "umformuliert"

export interface WordPiece {
  kind: "gleich" | "entfernt" | "hinzugefuegt"
  text: string
}

export interface DiffSegment {
  kind: DiffKind
  /** Satz im aktuellen Text (null bei «hinzugefügt»). */
  before: string | null
  /** Satz im Vorschlag (null bei «entfernt»). */
  after: string | null
  /** Offsets des before-Satzes im Ausgangstext (für applySegments). */
  beforeStart?: number
  beforeEnd?: number
  /** Einfügeposition im Ausgangstext — nur bei «hinzugefügt». */
  insertAfter?: number
  /** Wortweiser Inner-Diff — nur bei «umformuliert». */
  words?: WordPiece[]
}

// Ab dieser Wort-Überlappung (Jaccard) gilt ein Entfernt/Neu-Paar als
// Umformulierung desselben Satzes statt als zwei unabhängige Änderungen.
const REPHRASE_OVERLAP = 0.4

/** RUN 4B §3 — Zusammenfassung des Diffs in Nutzersprache (Screenreader und
 *  Sichttext identisch verwendbar). Zählt Sätze je Änderungsart. */
export function summarizeDiff(segments: DiffSegment[]): string {
  const added = segments.filter((s) => s.kind === "hinzugefuegt").length
  const removed = segments.filter((s) => s.kind === "entfernt").length
  const rephrased = segments.filter((s) => s.kind === "umformuliert").length
  if (added + removed + rephrased === 0) {
    return "Keine Änderungen gegenüber dem aktuellen Text."
  }
  const noun = (n: number) => (n === 1 ? "Satz" : "Sätze")
  const parts: string[] = []
  if (added > 0) parts.push(`${added} ${noun(added)} ergänzt`)
  if (removed > 0) parts.push(`${removed} ${noun(removed)} entfernt`)
  if (rephrased > 0) parts.push(`${rephrased} ${noun(rephrased)} umformuliert`)
  return `Änderungen im Vorschlag: ${parts.join(", ")}.`
}

interface SentenceToken {
  text: string
  start: number
  end: number
}

/** Sätze inkl. Satzzeichen und Offsets; Zeilenumbrüche trennen ebenfalls.
 *  Ein Punkt zählt nur als Satzende, wenn Whitespace oder das Textende folgt —
 *  Abschnittsmarker («4.2», «4.5.1») und Zahlen bleiben dadurch ganz. */
function splitSentences(text: string): SentenceToken[] {
  const tokens: SentenceToken[] = []
  const pushToken = (start: number, end: number) => {
    const raw = text.slice(start, end)
    const leading = raw.length - raw.trimStart().length
    const trimmed = raw.trim()
    if (trimmed.length === 0) return
    tokens.push({
      text: trimmed,
      start: start + leading,
      end: start + leading + trimmed.length,
    })
  }
  let sentenceStart = 0
  for (let i = 0; i < text.length; i++) {
    const char = text[i]
    if (char === "\n") {
      pushToken(sentenceStart, i)
      sentenceStart = i + 1
      continue
    }
    if (char === "." || char === "!" || char === "?") {
      // Folge-Satzzeichen («?!», «...») mitnehmen.
      let end = i + 1
      while (end < text.length && /[.!?]/.test(text[end])) end += 1
      const next = text[end]
      if (next === undefined || /\s/.test(next)) {
        pushToken(sentenceStart, end)
        sentenceStart = end
        i = end - 1
      }
    }
  }
  pushToken(sentenceStart, text.length)
  return tokens
}

function normalize(sentence: string): string {
  return sentence.toLowerCase().replace(/\s+/g, " ").trim()
}

function words(sentence: string): string[] {
  return sentence.split(/\s+/).filter(Boolean)
}

function wordOverlap(a: string, b: string): number {
  const setA = new Set(words(normalize(a)))
  const setB = new Set(words(normalize(b)))
  if (setA.size === 0 && setB.size === 0) return 1
  let shared = 0
  for (const token of setA) if (setB.has(token)) shared += 1
  const union = setA.size + setB.size - shared
  return union === 0 ? 0 : shared / union
}

/** Klassische LCS-Tabelle über Schlüssel-Arrays (O(n·m)). */
function lcsPairs(a: string[], b: string[]): Array<[number, number]> {
  const n = a.length
  const m = b.length
  // Für sehr lange Texte (Smoke: 25k Zeichen ≈ einige hundert Sätze) bleibt
  // die Tabelle klein genug; Uint32 hält den Speicher kompakt.
  const table = new Uint32Array((n + 1) * (m + 1))
  const idx = (i: number, j: number) => i * (m + 1) + j
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      table[idx(i, j)] =
        a[i] === b[j]
          ? table[idx(i + 1, j + 1)] + 1
          : Math.max(table[idx(i + 1, j)], table[idx(i, j + 1)])
    }
  }
  const pairs: Array<[number, number]> = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      pairs.push([i, j])
      i += 1
      j += 1
    } else if (table[idx(i + 1, j)] >= table[idx(i, j + 1)]) {
      i += 1
    } else {
      j += 1
    }
  }
  return pairs
}

/** Wortweiser Inner-Diff eines Umformulierungs-Paars. */
function wordDiff(before: string, after: string): WordPiece[] {
  const a = words(before)
  const b = words(after)
  const pairs = lcsPairs(
    a.map((w) => w.toLowerCase()),
    b.map((w) => w.toLowerCase())
  )
  const pieces: WordPiece[] = []
  let i = 0
  let j = 0
  const push = (kind: WordPiece["kind"], text: string) => {
    const last = pieces[pieces.length - 1]
    if (last && last.kind === kind) last.text += ` ${text}`
    else pieces.push({ kind, text })
  }
  for (const [pi, pj] of [...pairs, [a.length, b.length] as [number, number]]) {
    while (i < pi) push("entfernt", a[i++])
    while (j < pj) push("hinzugefuegt", b[j++])
    if (pi < a.length && pj < b.length) {
      push("gleich", a[pi])
      i = pi + 1
      j = pj + 1
    }
  }
  return pieces
}

/** Verbindet die Nicht-LCS-Lücken zwischen zwei Matches zu Segmenten. */
function gapSegments(
  removed: SentenceToken[],
  added: SentenceToken[],
  gapAnchor: number
): DiffSegment[] {
  const segments: DiffSegment[] = []
  const usedAdded = new Set<number>()
  for (const token of removed) {
    let bestIndex = -1
    let bestOverlap = 0
    added.forEach((candidate, index) => {
      if (usedAdded.has(index)) return
      const overlap = wordOverlap(token.text, candidate.text)
      if (overlap > bestOverlap) {
        bestOverlap = overlap
        bestIndex = index
      }
    })
    if (bestIndex >= 0 && bestOverlap >= REPHRASE_OVERLAP) {
      usedAdded.add(bestIndex)
      segments.push({
        kind: "umformuliert",
        before: token.text,
        after: added[bestIndex].text,
        beforeStart: token.start,
        beforeEnd: token.end,
        words: wordDiff(token.text, added[bestIndex].text),
      })
    } else {
      segments.push({
        kind: "entfernt",
        before: token.text,
        after: null,
        beforeStart: token.start,
        beforeEnd: token.end,
      })
    }
  }
  const insertAfter = removed.length > 0 ? removed[removed.length - 1].end : gapAnchor
  added.forEach((candidate, index) => {
    if (!usedAdded.has(index)) {
      segments.push({
        kind: "hinzugefuegt",
        before: null,
        after: candidate.text,
        insertAfter,
      })
    }
  })
  return segments
}

/** Satzweiser Vergleich Aktuell ↔ Vorschlag (C2). */
export function diffSuggestion(current: string, suggested: string): DiffSegment[] {
  const before = splitSentences(current)
  const after = splitSentences(suggested)
  const pairs = lcsPairs(
    before.map((t) => normalize(t.text)),
    after.map((t) => normalize(t.text))
  )

  const segments: DiffSegment[] = []
  let i = 0
  let j = 0
  let anchor = 0
  for (const [pi, pj] of [...pairs, [before.length, after.length] as [number, number]]) {
    if (i < pi || j < pj) {
      segments.push(...gapSegments(before.slice(i, pi), after.slice(j, pj), anchor))
      i = pi
      j = pj
    }
    if (pi < before.length && pj < after.length) {
      segments.push({
        kind: "beibehalten",
        before: before[pi].text,
        after: after[pj].text,
        beforeStart: before[pi].start,
        beforeEnd: before[pi].end,
      })
      anchor = before[pi].end
      i = pi + 1
      j = pj + 1
    }
  }
  return segments
}

/** Zusammenfassung für Kopf-/Aktionszeilen («n Änderungen»). */
export function countChanges(segments: DiffSegment[]): number {
  return segments.filter((s) => s.kind !== "beibehalten").length
}

/**
 * Wendet die AUSGEWÄHLTEN Änderungen auf den Ausgangstext an (C3 —
 * «einzelne Änderung übernehmen»). Unberührte Passagen bleiben
 * zeichenidentisch; nicht gewählte Segmente bleiben unverändert stehen.
 */
export function applySegments(
  current: string,
  segments: DiffSegment[],
  selected: ReadonlySet<number>
): string {
  interface Op {
    start: number
    end: number
    replacement: string
  }
  const ops: Op[] = []
  segments.forEach((segment, index) => {
    if (!selected.has(index) || segment.kind === "beibehalten") return
    if (segment.kind === "entfernt" && segment.beforeStart !== undefined) {
      // Auch nachfolgende Leerzeichen (nicht Zeilenumbrüche) mit entfernen.
      let end = segment.beforeEnd ?? segment.beforeStart
      while (end < current.length && (current[end] === " " || current[end] === "\t")) end += 1
      ops.push({ start: segment.beforeStart, end, replacement: "" })
    } else if (segment.kind === "umformuliert" && segment.beforeStart !== undefined) {
      ops.push({
        start: segment.beforeStart,
        end: segment.beforeEnd ?? segment.beforeStart,
        replacement: segment.after ?? "",
      })
    } else if (segment.kind === "hinzugefuegt" && segment.after) {
      const at = Math.min(segment.insertAfter ?? current.length, current.length)
      const needsSpace = at > 0 && !/\s/.test(current[at - 1] ?? "")
      ops.push({ start: at, end: at, replacement: `${needsSpace ? " " : ""}${segment.after}` })
    }
  })
  // Von hinten nach vorn anwenden, damit die Offsets gültig bleiben.
  ops.sort((a, b) => b.start - a.start || b.end - a.end)
  let result = current
  for (const op of ops) {
    result = result.slice(0, op.start) + op.replacement + result.slice(op.end)
  }
  return result
}
