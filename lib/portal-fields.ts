// Portal-field catalog client (Slice 4, E4-A): read-only view over ALL
// registry portal fields with a deterministic display mode. Additive —
// the M6 draft client (lib/fields.ts) stays untouched.

export type DisplayMode = "draft" | "checklist" | "upload" | "external_only"

export interface PortalFieldInfoDto {
  field_id: string
  section: string
  label: string
  character_limit?: number | null
  mandatory_status: string
  required?: boolean | null
  support_mode: string
  field_kind: string
  display_mode: DisplayMode
  draft_available: boolean
}

// User-facing badge labels — never show the technical mode values.
export const DISPLAY_MODE_LABELS: Record<DisplayMode, string> = {
  draft: "Textentwurf",
  checklist: "Im Portal manuell erfassen",
  upload: "Datei-Upload im Portal",
  external_only: "Im Portal beachten",
}

/** Badge label for one field; unsupported draft fields are called out. */
export function fieldModeLabel(field: PortalFieldInfoDto): string {
  if (field.display_mode === "draft" && !field.draft_available) {
    return "Textfeld im Portal — im MVP noch nicht unterstützt"
  }
  return DISPLAY_MODE_LABELS[field.display_mode]
}

export async function listPortalFields(
  runId: string
): Promise<PortalFieldInfoDto[]> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/portal-fields`
  )
  if (!res.ok) {
    throw new Error("Die Portalfeld-Übersicht konnte nicht geladen werden.")
  }
  return (await res.json()) as PortalFieldInfoDto[]
}
