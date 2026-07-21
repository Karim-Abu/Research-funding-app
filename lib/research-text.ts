export function normalizeResearchText(value: string): string {
  return value.normalize("NFC").trim()
}

export function unicodeLength(value: string): number {
  return Array.from(value.normalize("NFC")).length
}

export function parseSearchTags(value: string): string[] {
  const seen = new Set<string>()
  return value
    .split(",")
    .map(normalizeResearchText)
    .filter((item) => {
      const key = item.toLocaleLowerCase("de-CH")
      if (!item || seen.has(key)) return false
      seen.add(key)
      return true
    })
}
