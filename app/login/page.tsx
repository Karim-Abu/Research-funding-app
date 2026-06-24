"use client"

import * as React from "react"
import Image from "next/image"
import { useRouter } from "next/navigation"
import { Loader2, XCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert } from "@/components/ui/alert"
import { useSession } from "@/components/providers/app-providers"

// Login submits real credentials in live mode (POST /api/session via the BFF);
// in mock mode the session layer returns a stable demo identity.
export default function LoginPage() {
  const router = useRouter()
  const { login } = useSession()
  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (submitting) return
    if (!email.trim()) {
      setError(true)
      return
    }
    setError(false)
    setSubmitting(true)
    try {
      await login(email, password)
      router.push("/")
    } catch {
      setError(true)
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 px-4">
      <div className="flex w-full max-w-[400px] flex-col gap-4">
        <Card>
          <CardHeader className="flex flex-col items-center gap-3 pt-8 text-center">
            <span className="relative flex size-11 items-center justify-center overflow-hidden rounded-md">
              <Image src="/icon.png" alt="Logo" fill className="object-cover" priority />
            </span>
            <div className="flex flex-col gap-1">
              <h1 className="text-balance text-lg font-semibold text-foreground">
                Evidenzbasierte Proposal-Unterstützung
              </h1>
              <p className="text-sm text-muted-foreground">
                Interner Arbeitsbereich (Beta)
              </p>
            </div>
          </CardHeader>
          <CardContent className="pb-8">
            <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
              {error && (
                <Alert
                  role="alert"
                  className="flex items-start gap-3 border-destructive/30 bg-destructive/5 text-sm text-foreground"
                >
                  <XCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
                  <span>E-Mail oder Passwort ist nicht korrekt.</span>
                </Alert>
              )}

              <div className="flex flex-col gap-2">
                <Label htmlFor="login-email">E-Mail</Label>
                <Input
                  id="login-email"
                  type="email"
                  autoComplete="off"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={submitting}
                />
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="login-password">Passwort</Label>
                <Input
                  id="login-password"
                  type="password"
                  autoComplete="off"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={submitting}
                />
              </div>

              <Button type="submit" className="mt-2 w-full" disabled={submitting}>
                {submitting && <Loader2 data-icon="inline-start" className="animate-spin" />}
                {submitting ? "Anmelden…" : "Anmelden"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground">
          Zugang wird von Ihrer Projektleitung vergeben.
        </p>
      </div>
    </div>
  )
}
