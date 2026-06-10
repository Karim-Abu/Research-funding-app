"use client"

import { ShieldAlert } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Checkbox } from "@/components/ui/checkbox"

interface DataClassWarningProps {
  confirmed: boolean
  onConfirmedChange: (confirmed: boolean) => void
}

/** Destructive confirmation for 'internal' projects using cloud services. */
export function DataClassWarning({
  confirmed,
  onConfirmedChange,
}: DataClassWarningProps) {
  return (
    <Alert variant="destructive">
      <ShieldAlert />
      <AlertTitle>Dieses Projekt ist als intern eingestuft.</AlertTitle>
      <AlertDescription>
        <label className="flex items-start gap-2 text-sm">
          <Checkbox
            checked={confirmed}
            onCheckedChange={(c) => onConfirmedChange(c === true)}
            className="mt-0.5"
          />
          <span>
            Ich bestätige, dass keine vertraulichen Inhalte an externe Dienste
            übermittelt werden dürfen.
          </span>
        </label>
      </AlertDescription>
    </Alert>
  )
}
