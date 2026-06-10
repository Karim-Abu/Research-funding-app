import { FileText, Plus } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { MachineStatusBadge } from "@/components/status/machine-status-badge"
import { HumanCheckMark } from "@/components/status/human-check-mark"
import type { EvidenceAnchor } from "@/lib/editor-data"

interface EvidenceCardProps {
  evidence: EvidenceAnchor
}

/**
 * Compact evidence card. No confidence percentages anywhere.
 * Machine status as a colored badge; optional teal human check.
 */
export function EvidenceCard({ evidence }: EvidenceCardProps) {
  return (
    <Card className="gap-0 py-0">
      <CardContent className="flex flex-col gap-2 p-3">
        <div className="flex items-start gap-2">
          <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-sm font-medium text-foreground">
              {evidence.sourceTitle}
            </span>
            <span className="text-xs text-muted-foreground">
              {evidence.location}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <MachineStatusBadge status={evidence.status} />
          {evidence.humanCheck && (
            <HumanCheckMark check={evidence.humanCheck} />
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export { Plus as AddEvidenceIcon }
