"use client"

import * as React from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { RefreshCw } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { RequirementsScreen } from "@/components/anforderungen/requirements-screen"
import { LiveRequirements } from "@/components/anforderungen/live-requirements"
import { EvidenceTab } from "@/components/quellen/evidence-tab"
import { LiveEvidence } from "@/components/quellen/live-evidence"
import { ActiveRunDetails } from "@/components/status/active-run-details"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useSession } from "@/components/providers/app-providers"
import { useActiveRun } from "@/components/providers/workflow-run-provider"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { dummyEvidence } from "@/lib/quellen-mock-data"
import {
  getProjectState,
  ApiError,
  BRIDGE_UNREACHABLE_MESSAGE,
} from "@/lib/api"
import type { Requirement } from "@/lib/anforderungen-mock-data"

type AnalyseTab = "anforderungen" | "evidenz"

function tabFromParams(params: URLSearchParams): AnalyseTab {
  return params.get("tab") === "evidenz" ? "evidenz" : "anforderungen"
}

// Seitenkopf + Tabs «Anforderungen | Evidenz» — beide Ansichten gehören zum
// Schritt «Analyse & Recherche» und lesen denselben aktiven Run. Die
// Anforderungen-Ansicht bringt ihr eigenes Seitenlayout mit (kein doppeltes
// Padding); die Evidenz-Ansicht wird hier eingepasst.
function AnalysePageFrame({
  tab,
  onTabChange,
  anforderungen,
  evidenz,
}: {
  tab: AnalyseTab
  onTabChange: (tab: AnalyseTab) => void
  anforderungen: React.ReactNode
  evidenz: React.ReactNode
}) {
  return (
    <Tabs
      value={tab}
      onValueChange={(value) => onTabChange(value as AnalyseTab)}
    >
      <div className="mx-auto w-full max-w-4xl px-6 pt-8">
        <div className="flex flex-col gap-2">
          <h1 className="text-balance text-2xl font-semibold text-foreground">
            Analyse &amp; Recherche
          </h1>
          <p className="text-sm text-muted-foreground">
            Ergebnisse der Analyse: Fördervoraussetzungen und gefundene Belege —
            beides bezieht sich auf denselben Analyse-Lauf.
          </p>
        </div>
        <TabsList className="mt-4">
          <TabsTrigger value="anforderungen">Anforderungen</TabsTrigger>
          <TabsTrigger value="evidenz">Evidenz</TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="anforderungen">{anforderungen}</TabsContent>
      <TabsContent value="evidenz">
        <div className="mx-auto w-full max-w-4xl px-6 py-6">{evidenz}</div>
      </TabsContent>
    </Tabs>
  )
}

// --- Live mode: render the run-scoped RequirementAssessments ----------------
function LiveAnalyseContainer() {
  const router = useRouter()
  // Deep links (?requirement=…, ?anchor=…, ?tab=evidenz) — parsed here (not in
  // LiveRequirements) so component tests don't need a router mock.
  const searchParams = useSearchParams()
  const focusRequirementId = searchParams.get("requirement")
  const focusAnchorId = searchParams.get("anchor")
  const tab = tabFromParams(searchParams)
  const { runId, source, loading } = useActiveRun()

  const handleTabChange = React.useCallback(
    (next: AnalyseTab) => {
      router.replace(
        next === "evidenz" ? "/anforderungen?tab=evidenz" : "/anforderungen"
      )
    },
    [router]
  )

  if (loading) return null
  if (!runId) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16 text-center">
        <p className="text-sm text-muted-foreground">
          Es liegt noch keine abgeschlossene Analyse vor. Starten Sie zunächst
          unter «Quellen» eine Analyse.
        </p>
        <Button
          variant="outline"
          className="mt-4"
          onClick={() => router.push("/quellen")}
        >
          Zu den Quellen — Analyse starten
        </Button>
      </div>
    )
  }
  return (
    <>
      <AnalysePageFrame
        tab={tab}
        onTabChange={handleTabChange}
        anforderungen={
          <LiveRequirements
            runId={runId}
            focusRequirementId={focusRequirementId}
          />
        }
        evidenz={
          <LiveEvidence
            runId={runId}
            focusAnchorId={focusAnchorId}
            onOpenSource={(sourceId) =>
              router.push(`/quellen?source=${encodeURIComponent(sourceId)}`)
            }
          />
        }
      />
      <div className="mx-auto w-full max-w-4xl px-6 pb-8">
        <ActiveRunDetails runId={runId} source={source} />
      </div>
    </>
  )
}

// --- Mock mode: unchanged elaborate mock screen -----------------------------
function MockAnalyse() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const tab = tabFromParams(searchParams)
  const [requirements, setRequirements] = React.useState<Requirement[] | null>(
    null
  )
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(() => {
    let cancelled = false
    setError(null)
    setRequirements(null)
    getProjectState(activeProjectId)
      .then((state) => {
        if (!cancelled) setRequirements(state.requirements)
      })
      .catch((e) => {
        if (!cancelled)
          setError(
            e instanceof ApiError ? e.message : BRIDGE_UNREACHABLE_MESSAGE
          )
      })
    return () => {
      cancelled = true
    }
  }, [])

  React.useEffect(() => load(), [load])

  const handleTabChange = React.useCallback(
    (next: AnalyseTab) => {
      router.replace(
        next === "evidenz" ? "/anforderungen?tab=evidenz" : "/anforderungen"
      )
    },
    [router]
  )

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10">
        <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-16 text-center">
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button variant="outline" onClick={load}>
            <RefreshCw data-icon="inline-start" />
            Erneut versuchen
          </Button>
        </div>
      </div>
    )
  }
  return (
    <AnalysePageFrame
      tab={tab}
      onTabChange={handleTabChange}
      anforderungen={
        requirements === null ? (
          <RequirementsScreen key="loading" forceState="loading" />
        ) : (
          <RequirementsScreen key="loaded" requirements={requirements} />
        )
      }
      evidenz={<EvidenceTab cards={dummyEvidence} />}
    />
  )
}

export default function AnforderungenPage() {
  const { mode } = useSession()
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
    >
      {/* useSearchParams requires a Suspense boundary in the App Router. */}
      <React.Suspense fallback={null}>
        {mode === "live" ? <LiveAnalyseContainer /> : <MockAnalyse />}
      </React.Suspense>
    </AppShell>
  )
}
