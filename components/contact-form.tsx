"use client"

import * as React from "react"
import { CheckCircle2, Loader2, XCircle } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

type ContactFormProps = {
  onSuccess?: () => void
}

export function ContactForm({ onSuccess }: ContactFormProps) {
  const [name, setName] = React.useState("")
  const [email, setEmail] = React.useState("")
  const [subject, setSubject] = React.useState("")
  const [message, setMessage] = React.useState("")
  const [errors, setErrors] = React.useState<Record<string, boolean>>({})
  const [submitting, setSubmitting] = React.useState(false)
  const [submitted, setSubmitted] = React.useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (submitting) return

    const nextErrors = {
      name: !name.trim(),
      email: !EMAIL_PATTERN.test(email.trim()),
      message: !message.trim(),
    }
    setErrors(nextErrors)
    if (Object.values(nextErrors).some(Boolean)) return

    setSubmitting(true)
    // No support-request backend exists yet; simulate the round trip so the
    // form is demoable end-to-end without fabricating a fake API route.
    await new Promise((resolve) => setTimeout(resolve, 600))
    setSubmitting(false)
    setSubmitted(true)
    onSuccess?.()
  }

  if (submitted) {
    return (
      <Alert className="flex items-start gap-3">
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
        <span>
          Danke, {name.trim().split(" ")[0]}! Ihre Nachricht wurde übermittelt —
          wir melden uns bei Ihnen unter {email}.
        </span>
      </Alert>
    )
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Label htmlFor="contact-name">Name</Label>
          <Input
            id="contact-name"
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-invalid={errors.name}
            disabled={submitting}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="contact-email">E-Mail</Label>
          <Input
            id="contact-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={errors.email}
            disabled={submitting}
          />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="contact-subject">Betreff</Label>
        <Input
          id="contact-subject"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          disabled={submitting}
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="contact-message">Nachricht</Label>
        <Textarea
          id="contact-message"
          rows={4}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          aria-invalid={errors.message}
          disabled={submitting}
        />
      </div>

      {Object.values(errors).some(Boolean) && (
        <Alert
          role="alert"
          variant="destructive"
          className="flex items-start gap-3"
        >
          <XCircle className="mt-0.5 size-4 shrink-0" />
          <span>Bitte füllen Sie Name, eine gültige E-Mail und Ihre Nachricht aus.</span>
        </Alert>
      )}

      <Button type="submit" className="w-full sm:w-auto" disabled={submitting}>
        {submitting && <Loader2 data-icon="inline-start" className="animate-spin" />}
        {submitting ? "Wird gesendet…" : "Nachricht senden"}
      </Button>
    </form>
  )
}
