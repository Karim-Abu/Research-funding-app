"use client"

import * as React from "react"
import { usePathname, useRouter } from "next/navigation"
import {
  getBackendMode,
  setBackendMode,
  type BackendMode,
} from "@/lib/app-mode"
import {
  bootstrapSession,
  login as apiLogin,
  logout as apiLogout,
  type SessionUser,
} from "@/lib/session"
import { clearAllRichEditorSessionCache } from "@/lib/rich-editor-cache"
import { clearIntakeSession } from "@/lib/intake-store"

type Status = "loading" | "authenticated" | "unauthenticated"

interface SessionContextValue {
  mode: BackendMode
  status: Status
  user: SessionUser | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const SessionContext = React.createContext<SessionContextValue | null>(null)

export function useSession(): SessionContextValue {
  const ctx = React.useContext(SessionContext)
  if (!ctx) {
    throw new Error("useSession must be used within <AppProviders>")
  }
  return ctx
}

export function AppProviders({
  mode,
  children,
}: {
  mode: BackendMode
  children: React.ReactNode
}) {
  // Single, server-controlled source of truth for the backend mode.
  setBackendMode(mode)

  const router = useRouter()
  const pathname = usePathname()
  const [status, setStatus] = React.useState<Status>("loading")
  const [user, setUser] = React.useState<SessionUser | null>(null)

  React.useEffect(() => {
    let active = true
    bootstrapSession()
      .then((u) => {
        if (!active) return
        setUser(u)
        setStatus(u ? "authenticated" : "unauthenticated")
      })
      .catch(() => {
        if (!active) return
        setUser(null)
        setStatus("unauthenticated")
      })
    return () => {
      active = false
    }
  }, [])

  // Live mode only: send unauthenticated users to the login screen.
  React.useEffect(() => {
    if (getBackendMode() !== "live") return
    if (status === "unauthenticated" && pathname !== "/login") {
      router.replace("/login")
    }
  }, [status, pathname, router])

  const login = React.useCallback(
    async (email: string, password: string) => {
      const u = await apiLogin(email, password)
      setUser(u)
      setStatus("authenticated")
    },
    []
  )

  const logout = React.useCallback(async () => {
    await apiLogout()
    // Proposal text lives in the rich-editor session cache — clear it on logout.
    clearAllRichEditorSessionCache()
    // R4.4: das Intake (Projektidee, Budget, Partner) ist ebenfalls ein
    // Inhalts-Key — beim Logout vollständig entfernen.
    clearIntakeSession()
    setUser(null)
    setStatus("unauthenticated")
  }, [])

  const value = React.useMemo<SessionContextValue>(
    () => ({ mode, status, user, login, logout }),
    [mode, status, user, login, logout]
  )

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  )
}
