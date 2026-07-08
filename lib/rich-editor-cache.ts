// Session-only cache for the Tiptap rich-text state of the Entwurf editor.
//
// The backend stores ONLY plain text. To let formatting survive a field switch
// or a reload within the same browser session, we keep the Tiptap JSON in
// sessionStorage (never localStorage) keyed by project + field, and guarded by a
// hash of the server plain text so a stale cache is discarded automatically.
//
// Governance (CLAUDEX §7, R4.4 / Owner-Tabelle §6): the cached JSON contains
// proposal text and is treated exactly like the draft — it lives only in
// sessionStorage (gone when the tab closes), is cleared on logout / project
// switch / explicit user action, is allowed ONLY for explicitly public (D0)
// projects (internal/confidential/nda/unknown are fail-closed), and is NEVER
// logged.

import type { JSONContent } from "@tiptap/react"
import { normalizePortalPlainText } from "./rich-editor-content"

const SCHEMA_VERSION = 1
const KEY_PREFIX = "rf_rich_editor_v1"

export interface RichEditorCacheEntry {
  schemaVersion: number
  projectId: string
  fieldId: string
  serverTextHash: string
  plainTextSnapshot: string
  tiptapJson: JSONContent
  updatedAt: string
}

function storage(): Storage | null {
  if (typeof window === "undefined") return null
  try {
    return window.sessionStorage
  } catch {
    return null // storage blocked (privacy settings)
  }
}

/** Fast, stable 32-bit string hash (djb2-xor) rendered as hex. Not crypto. */
export function hashServerText(text: string): string {
  const normalized = normalizePortalPlainText(text)
  let h = 5381
  for (let i = 0; i < normalized.length; i++) {
    h = ((h << 5) + h) ^ normalized.charCodeAt(i)
  }
  // >>> 0 → unsigned; include length to further reduce collisions.
  return `${(h >>> 0).toString(16)}-${normalized.length.toString(16)}`
}

export function getRichEditorCacheKey(projectId: string, fieldId: string): string {
  return `${KEY_PREFIX}:${projectId}:${fieldId}`
}

/**
 * Data-class gate (R4.4, Security-P0 S1). Der Komfort-Cache ist NUR für
 * explizit öffentliche (D0) Projekte erlaubt. Internal/confidential/nda sowie
 * fehlende oder unbekannte Einstufungen sind fail-closed — kein Tiptap-JSON
 * mit Inhalt im Browser-Storage.
 */
export function isRichCacheAllowed(dataClass?: string | null): boolean {
  if (!dataClass) return false
  return /^(public|d0)$/i.test(dataClass.trim())
}

/**
 * Return the cached entry only when it matches this project/field AND the server
 * text is unchanged (hash match). Any mismatch discards the stale entry.
 */
export function readRichEditorSessionCache(
  projectId: string,
  fieldId: string,
  serverTextHash: string
): RichEditorCacheEntry | null {
  const store = storage()
  if (!store) return null
  const key = getRichEditorCacheKey(projectId, fieldId)
  const raw = store.getItem(key)
  if (!raw) return null
  try {
    const entry = JSON.parse(raw) as RichEditorCacheEntry
    if (
      entry.schemaVersion !== SCHEMA_VERSION ||
      entry.projectId !== projectId ||
      entry.fieldId !== fieldId ||
      entry.serverTextHash !== serverTextHash ||
      !entry.tiptapJson
    ) {
      store.removeItem(key) // stale / incompatible → drop it
      return null
    }
    return entry
  } catch {
    store.removeItem(key)
    return null
  }
}

export function writeRichEditorSessionCache(params: {
  projectId: string
  fieldId: string
  serverTextHash: string
  plainTextSnapshot: string
  tiptapJson: JSONContent
}): void {
  const store = storage()
  if (!store) return
  const entry: RichEditorCacheEntry = {
    schemaVersion: SCHEMA_VERSION,
    projectId: params.projectId,
    fieldId: params.fieldId,
    serverTextHash: params.serverTextHash,
    plainTextSnapshot: params.plainTextSnapshot,
    tiptapJson: params.tiptapJson,
    updatedAt: new Date().toISOString(),
  }
  try {
    store.setItem(getRichEditorCacheKey(params.projectId, params.fieldId), JSON.stringify(entry))
  } catch {
    // Quota or serialization failure — formatting is a convenience; ignore.
  }
}

export function clearRichEditorSessionCache(projectId: string, fieldId: string): void {
  storage()?.removeItem(getRichEditorCacheKey(projectId, fieldId))
}

/** R4.4: remove every entry of ONE project (Alt-Cache-Bereinigung, wenn ein
 *  nicht-öffentliches Projekt geladen wird). */
export function clearProjectRichEditorSessionCache(projectId: string): void {
  const store = storage()
  if (!store) return
  try {
    const prefix = `${KEY_PREFIX}:${projectId}:`
    const keys: string[] = []
    for (let i = 0; i < store.length; i++) {
      const k = store.key(i)
      if (k && k.startsWith(prefix)) keys.push(k)
    }
    for (const k of keys) store.removeItem(k)
  } catch {
    /* storage blocked */
  }
}

/** Remove every rich-editor entry (logout / project switch). */
export function clearAllRichEditorSessionCache(): void {
  const store = storage()
  if (!store) return
  try {
    const keys: string[] = []
    for (let i = 0; i < store.length; i++) {
      const k = store.key(i)
      if (k && k.startsWith(`${KEY_PREFIX}:`)) keys.push(k)
    }
    for (const k of keys) store.removeItem(k)
  } catch {
    /* storage blocked */
  }
}
