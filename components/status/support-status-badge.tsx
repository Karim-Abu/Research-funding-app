import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  FileSearch,
  HelpCircle,
  ShieldAlert,
  UserCheck,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  SUPPORT_STATUS_LABELS,
  SUPPORT_STATUS_SHORT_LABELS,
  SUPPORT_STATUS_STYLES,
  type SupportStatus,
} from "@/lib/evidence-ladder"

const ICONS: Record<SupportStatus, typeof CheckCircle2> = {
  not_required: Circle,
  evidence_missing: HelpCircle,
  location_found: FileSearch,
  supports_partially: AlertTriangle,
  supports_strongly: CheckCircle2,
  conflict_or_uncertain: ShieldAlert,
  human_review_required: UserCheck,
}

interface SupportStatusBadgeProps {
  status: SupportStatus
  /** Kurzlabel für enge Listen statt des vollen Leiter-Labels. */
  short?: boolean
  className?: string
}

/** R6-Statusleiter-Badge. Grün ausschliesslich bei supports_strongly;
 * location_found rendert neutral — Coverage, keine fachliche Verifikation. */
export function SupportStatusBadge({
  status,
  short = false,
  className,
}: SupportStatusBadgeProps) {
  const Icon = ICONS[status]
  const label = short
    ? SUPPORT_STATUS_SHORT_LABELS[status]
    : SUPPORT_STATUS_LABELS[status]
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        SUPPORT_STATUS_STYLES[status],
        className
      )}
    >
      <Icon className="size-3.5 shrink-0" />
      {label}
    </span>
  )
}
