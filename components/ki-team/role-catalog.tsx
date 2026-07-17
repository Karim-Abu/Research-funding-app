"use client"

import { getRoleCatalogGroups, type KiTeamRole } from "@/lib/ki-team-data"
import { RoleCard } from "./role-card"

const groups = getRoleCatalogGroups()

interface RoleCatalogProps {
  openInstanceId: string | null
  onOpenRole: (
    role: KiTeamRole,
    instanceId: string,
    element: HTMLButtonElement
  ) => void
}

export function RoleCatalog({
  openInstanceId,
  onOpenRole,
}: Readonly<RoleCatalogProps>) {
  return (
    <section aria-labelledby="role-catalog-title">
      <div className="mb-6">
        <h2
          id="role-catalog-title"
          className="font-heading text-lg font-semibold text-foreground"
        >
          Funktionen im Überblick
        </h2>
        <p className="mt-1 max-w-3xl text-sm leading-relaxed text-muted-foreground">
          Jede Funktion erscheint hier einmal. Die Modusangabe zeigt, ob KI,
          feste Regeln oder beide zusammen eingesetzt werden.
        </p>
      </div>

      <div className="flex flex-col gap-8">
        {groups.map((group) => (
          <section key={group.category} aria-labelledby={`${group.category}-title`}>
            <div className="mb-3">
              <h3
                id={`${group.category}-title`}
                className="font-heading text-base font-semibold text-foreground"
              >
                {group.title}
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {group.category === "specialist"
                  ? "Unterstützen Analyse, Entwurf, Prüfung und Export."
                  : "Sichern Ablauf, Datenzugriff und kontrollierte Recherche."}
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {group.roles.map((role) => {
                const instanceId = `catalog-${role.id}`
                return (
                  <RoleCard
                    key={role.id}
                    role={role}
                    instanceId={instanceId}
                    expanded={openInstanceId === instanceId}
                    variant="catalog"
                    onOpen={onOpenRole}
                  />
                )
              })}
            </div>
          </section>
        ))}
      </div>
    </section>
  )
}
