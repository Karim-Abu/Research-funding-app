"use client"

// Fehleranzeige für Upload-/Quellen-/Import-Vorgänge: verständliche Meldung,
// «Erneut versuchen» und die technischen Angaben (Fehlercode, HTTP-Status,
// Correlation-ID) ausschliesslich eingeklappt unter «Technische Details» —
// rohe Codes erscheinen nie in der Standardansicht (CLAUDEX §2/§5).

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"

export interface UploadErrorInfo {
  message: string
  code?: string
  status?: number
  correlationId?: string | null
}

/** Extrahiert die sicheren Fehler-Metadaten aus SourceError/ImportError. */
export function toUploadErrorInfo(
  err: unknown,
  fallback: string
): UploadErrorInfo {
  if (err instanceof Error) {
    const details = err as Error & {
      code?: string
      status?: number
      correlationId?: string | null
    }
    return {
      message: err.message || fallback,
      code: typeof details.code === "string" ? details.code : undefined,
      status: typeof details.status === "number" ? details.status : undefined,
      correlationId: details.correlationId ?? null,
    }
  }
  return { message: fallback }
}

export function UploadErrorNotice({
  error,
  onRetry,
  retryDisabled,
}: Readonly<{
  error: UploadErrorInfo
  onRetry?: () => void
  retryDisabled?: boolean
}>) {
  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2">
      <p role="alert" className="text-sm text-destructive">
        {error.message}
      </p>
      {onRetry && (
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="mt-2"
          onClick={onRetry}
          disabled={retryDisabled}
        >
          Erneut versuchen
        </Button>
      )}
      <Accordion className="mt-1">
        <AccordionItem value="technische-details">
          <AccordionTrigger>Technische Details</AccordionTrigger>
          <AccordionContent>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <dt className="text-muted-foreground">Fehlercode</dt>
              <dd>
                <code className="rounded bg-muted px-1.5 py-0.5">
                  {error.code ?? "—"}
                </code>
              </dd>
              <dt className="text-muted-foreground">HTTP-Status</dt>
              <dd>{error.status ? String(error.status) : "—"}</dd>
              <dt className="text-muted-foreground">Correlation-ID</dt>
              <dd>
                <code className="rounded bg-muted px-1.5 py-0.5 break-all">
                  {error.correlationId ?? "—"}
                </code>
              </dd>
            </dl>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  )
}
