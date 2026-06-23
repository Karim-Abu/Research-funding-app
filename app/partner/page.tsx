"use client"

import { PlaceholderScreen } from "@/components/shell/placeholder-screen"
import { PartnerManager } from "@/components/partner/partner-manager"
import { useSession } from "@/components/providers/app-providers"

export default function Page() {
  const { mode } = useSession()
  // Live mode: manage real consortium partners (drives the formal precheck).
  // Mock mode keeps the existing placeholder untouched.
  if (mode === "live") return <PartnerManager />
  return (
    <PlaceholderScreen
      title="Partner & Rollen"
      description="Konsortialpartner und Zugriffsrollen verwalten. Dieser Bereich folgt in einem späteren Schritt."
    />
  )
}
