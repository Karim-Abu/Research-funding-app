// Strict placeholder syntax shared with backend/app/drafts/templates.py.
// Do not broaden this for UI convenience; draft-view keeps a separate broad matcher.
const STRICT_PLACEHOLDER_PATTERN = String.raw`\[\[Angabe ergänzen:[^\]]*\]\]`
const STRICT_PLACEHOLDER_RE = new RegExp(STRICT_PLACEHOLDER_PATTERN)
const STRICT_PLACEHOLDER_RE_GLOBAL = new RegExp(STRICT_PLACEHOLDER_PATTERN, "g")

export function hasPlaceholder(text: string): boolean {
  return STRICT_PLACEHOLDER_RE.test(text)
}

export function countPlaceholders(text: string): number {
  return [...text.matchAll(STRICT_PLACEHOLDER_RE_GLOBAL)].length
}

// Spiegel von backend/app/drafts/templates.py::is_placeholder_only — Erst-Entwurf,
// wenn nach dem Entfernen der Vorlagen-Platzhalter nichts Substanzielles bleibt.
export function isPlaceholderOnly(text: string): boolean {
  return text.replace(STRICT_PLACEHOLDER_RE_GLOBAL, "").trim() === ""
}