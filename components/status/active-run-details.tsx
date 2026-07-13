"use client"

// «Technische Details» für den aktiven Analyse-Lauf: die Roh-Run-ID erscheint
// nirgends in der Standardansicht — nur hier, eingeklappt, zusammen mit der
// Auswahlquelle der Run-Auswahl-Ladder (lib/active-run.ts).

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import {
  ACTIVE_RUN_SOURCE_LABELS,
  type ActiveRunSource,
} from "@/lib/active-run"

export function ActiveRunDetails({
  runId,
  source,
}: {
  runId: string
  source: ActiveRunSource | null
}) {
  return (
    <Accordion>
      <AccordionItem value="technische-details">
        <AccordionTrigger>Technische Details</AccordionTrigger>
        <AccordionContent>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <dt className="text-muted-foreground">Analyse-Lauf</dt>
            <dd>
              <code className="rounded bg-muted px-1.5 py-0.5">{runId}</code>
            </dd>
            <dt className="text-muted-foreground">Auswahlquelle</dt>
            <dd>{source ? ACTIVE_RUN_SOURCE_LABELS[source] : "—"}</dd>
          </dl>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
