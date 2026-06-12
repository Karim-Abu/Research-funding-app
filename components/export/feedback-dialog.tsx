"use client"

import * as React from "react"
import { CheckCircle2, Loader2, XCircle } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  submitFeedback,
  ApiError,
  BRIDGE_UNREACHABLE_MESSAGE,
} from "@/lib/api"
import type { FeedbackDto, FeedbackScale } from "@/lib/backend-contract"

// Beta-Feedback: 4 Skalen (1-5) + 2 optionale Freitexte.
// Keine personenbezogenen Daten, nichts ist Pflicht ausser den Skalen.

const SCALE_QUESTIONS: Array<{
  key: keyof Pick<
    FeedbackDto,
    "verstaendlichkeit" | "nuetzlichkeit" | "vertrauenBelege" | "hitlAufwand"
  >
  label: string
}> = [
  { key: "verstaendlichkeit", label: "Verständlichkeit" },
  { key: "nuetzlichkeit", label: "Nützlichkeit" },
  { key: "vertrauenBelege", label: "Vertrauen in die Belege" },
  { key: "hitlAufwand", label: "Aufwand der manuellen Prüfung" },
]

const SCALE_VALUES: FeedbackScale[] = [1, 2, 3, 4, 5]

type ScaleAnswers = Partial<Record<(typeof SCALE_QUESTIONS)[number]["key"], FeedbackScale>>

interface FeedbackDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function FeedbackDialog({ open, onOpenChange }: FeedbackDialogProps) {
  const [scales, setScales] = React.useState<ScaleAnswers>({})
  const [hilfreich, setHilfreich] = React.useState("")
  const [verbessern, setVerbessern] = React.useState("")
  const [submitting, setSubmitting] = React.useState(false)
  const [submitted, setSubmitted] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const allScalesAnswered = SCALE_QUESTIONS.every((q) => scales[q.key])

  function reset() {
    setScales({})
    setHilfreich("")
    setVerbessern("")
    setSubmitted(false)
    setError(null)
  }

  async function handleSubmit() {
    if (!allScalesAnswered || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      await submitFeedback({
        verstaendlichkeit: scales.verstaendlichkeit!,
        nuetzlichkeit: scales.nuetzlichkeit!,
        vertrauenBelege: scales.vertrauenBelege!,
        hitlAufwand: scales.hitlAufwand!,
        hilfreich: hilfreich.trim(),
        verbessern: verbessern.trim(),
      })
      setSubmitted(true)
    } catch (e) {
      // Eingaben bleiben erhalten.
      setError(e instanceof ApiError ? e.message : BRIDGE_UNREACHABLE_MESSAGE)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next)
        if (!next) reset()
      }}
    >
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Beta-Feedback</DialogTitle>
          <DialogDescription>
            Ihre Rückmeldung hilft, die Beta zu verbessern. Es werden keine
            personenbezogenen Daten erhoben.
          </DialogDescription>
        </DialogHeader>

        {submitted ? (
          <div className="flex items-center gap-2 rounded-md border border-human/30 bg-human/8 px-4 py-3 text-sm text-foreground">
            <CheckCircle2 className="size-4 shrink-0 text-human" />
            Danke — Ihr Feedback wurde gespeichert.
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            {error && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-foreground"
              >
                <XCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
                {error}
              </div>
            )}

            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between gap-4">
                <span className="text-xs text-muted-foreground">
                  1 = sehr gering · 5 = sehr hoch
                </span>
              </div>
              {SCALE_QUESTIONS.map((q) => (
                <div
                  key={q.key}
                  className="flex items-center justify-between gap-4"
                >
                  <span className="text-sm text-foreground">{q.label}</span>
                  <RadioGroup
                    value={scales[q.key] != null ? String(scales[q.key]) : ""}
                    onValueChange={(v) =>
                      setScales((prev) => ({
                        ...prev,
                        [q.key]: Number(v) as FeedbackScale,
                      }))
                    }
                    className="flex flex-row gap-2"
                    aria-label={q.label}
                  >
                    {SCALE_VALUES.map((value) => (
                      <label
                        key={value}
                        className="flex cursor-pointer items-center gap-1 text-xs text-muted-foreground"
                      >
                        <RadioGroupItem
                          value={String(value)}
                          id={`fb-${q.key}-${value}`}
                        />
                        {value}
                      </label>
                    ))}
                  </RadioGroup>
                </div>
              ))}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fb-hilfreich">Was war hilfreich?</Label>
              <Textarea
                id="fb-hilfreich"
                value={hilfreich}
                onChange={(e) => setHilfreich(e.target.value)}
                className="min-h-[70px]"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fb-verbessern">Was sollte verbessert werden?</Label>
              <Textarea
                id="fb-verbessern"
                value={verbessern}
                onChange={(e) => setVerbessern(e.target.value)}
                className="min-h-[70px]"
              />
            </div>
          </div>
        )}

        <DialogFooter>
          {submitted ? (
            <Button onClick={() => onOpenChange(false)}>Schliessen</Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Abbrechen
              </Button>
              <Button
                disabled={!allScalesAnswered || submitting}
                onClick={handleSubmit}
              >
                {submitting && (
                  <Loader2 data-icon="inline-start" className="animate-spin" />
                )}
                {submitting ? "Wird gesendet…" : "Feedback senden"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
