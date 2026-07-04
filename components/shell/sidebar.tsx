"use client"

import type { ReactNode } from "react"
import Image from "next/image"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  FolderKanban,
  FilePlus2,
  Ticket,
  MoreHorizontal,
  Landmark,
  Globe,
  LayoutDashboard,
  ClipboardList,
  Database,
  ListChecks,
  FileSearch,
  PenLine,
  CheckSquare,
  Download,
  Wallet,
  PanelLeftClose,
  PanelLeftOpen,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { Role } from "@/lib/types"

interface NavLink {
  label: string
  href: string
  icon: LucideIcon
}

interface DisabledLink {
  label: string
  icon?: LucideIcon
}

// "Aktueller Antrag" — the guided workflow for the active application.
// Note: Quellen and Evidenz share the /quellen route (tabbed); Entwurf maps to
// the editor. "Übersicht" points at the projects overview until a dedicated
// per-application overview route exists (frontend fallback, no API change).
const currentApplication: NavLink[] = [
  { label: "Übersicht", href: "/", icon: LayoutDashboard },
  { label: "Intake", href: "/intake", icon: ClipboardList },
  { label: "Quellen", href: "/quellen", icon: Database },
  { label: "Anforderungen", href: "/anforderungen", icon: ListChecks },
  { label: "Evidenz", href: "/quellen?tab=evidenz", icon: FileSearch },
  { label: "Entwurf", href: "/editor", icon: PenLine },
  { label: "Qualitätsprüfung", href: "/review", icon: CheckSquare },
  // Innolink-Übernahme (/portal-transfer) zieht später unter "Export" — die
  // Route bleibt vorerst erhalten, der Sidebar-Eintrag folgt im nächsten Schritt.
  { label: "Export", href: "/export", icon: Download },
  { label: "Kosten & Laufzeit (Demo)", href: "/kosten", icon: Wallet },
]

// Icon rail shown when the sidebar is collapsed — only navigable workflow items.
const collapsedItems: NavLink[] = [
  { label: "Projekte", href: "/", icon: FolderKanban },
  ...currentApplication.filter((i) => i.label !== "Übersicht"),
]

interface SidebarProps {
  role: Role
  collapsed: boolean
  onToggle: () => void
  /** Title of the active Antrag; null → project-scoped links are disabled. */
  activeProjectTitle?: string | null
  /** User-facing status line for the active Antrag (e.g. "In Bearbeitung"). */
  activeProjectStatusLabel?: string | null
}

function pathActive(pathname: string, href: string): boolean {
  const path = href.split("?")[0]
  if (path === "/") return pathname === "/"
  return pathname === path || pathname.startsWith(`${path}/`)
}

// Links that work without a selected Antrag (overview + creating a new one).
const PROJECT_INDEPENDENT = new Set(["Übersicht", "Intake"])

export function Sidebar({
  collapsed,
  onToggle,
  activeProjectTitle = null,
  activeProjectStatusLabel = null,
}: SidebarProps) {
  const pathname = usePathname()
  const hasProject = activeProjectTitle !== null && activeProjectTitle !== ""
  const navigationId = "primary-sidebar-navigation"
  const toggleLabel = collapsed ? "Erweitern" : "Minimieren"

  return (
    <aside
      className={cn(
        "relative flex shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200",
        collapsed ? "w-16" : "w-60"
      )}
    >
      <div
        className={cn(
          "flex h-16 items-center border-b border-sidebar-border",
          collapsed ? "justify-center px-2" : "px-4"
        )}
      >
        <Link href="/" className="flex items-center gap-2 outline-none">
          <span className="relative flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-md">
            <Image src="/icon.png" alt="Logo" fill className="object-cover" />
          </span>
          {!collapsed && (
            <span className="text-sm font-semibold leading-tight text-sidebar-foreground">
              Innosuisse-Antrag
            </span>
          )}
        </Link>
      </div>

      <nav
        id={navigationId}
        aria-label="Hauptnavigation"
        className="flex flex-1 flex-col gap-1 overflow-y-auto p-2 pb-16"
      >
        {collapsed ? (
          collapsedItems.map((item) =>
            hasProject || PROJECT_INDEPENDENT.has(item.label) || item.label === "Projekte" ? (
              <CollapsedLink
                key={item.label}
                item={item}
                active={pathActive(pathname, item.href)}
              />
            ) : (
              <CollapsedDisabled key={item.label} item={item} />
            )
          )
        ) : (
          <>
            {/* Projekte */}
            <ExpandedLink
              item={{ label: "Projekte", href: "/", icon: FolderKanban }}
              active={pathname === "/"}
            />

            {/* Funding Programme */}
            <SectionLabel>Funding Programme</SectionLabel>
            <GroupLabel>Innosuisse</GroupLabel>
            <ExpandedLink
              item={{
                label: "Create Innovation Project",
                href: "/intake",
                icon: FilePlus2,
              }}
              active={pathActive(pathname, "/intake")}
              badge="Aktiv"
            />
            <DisabledRow
              item={{ label: "Create Innovation Cheque", icon: Ticket }}
            />
            <DisabledRow
              item={{ label: "Weitere Programme", icon: MoreHorizontal }}
            />
            <DisabledRow item={{ label: "SNF", icon: Landmark }} />
            <DisabledRow item={{ label: "Horizon Europe", icon: Globe }} />

            {/* Aktueller Antrag — compact card naming the selected
                application; the workflow links below always refer to it. */}
            <SectionLabel>Aktueller Antrag</SectionLabel>
            <div
              data-testid="sidebar-active-project"
              className={cn(
                "mx-1 mb-1 rounded-md border px-2.5 py-2",
                hasProject
                  ? "border-sidebar-border bg-sidebar-accent/50"
                  : "border-dashed border-sidebar-border"
              )}
            >
              {hasProject ? (
                <>
                  <p
                    className="truncate text-xs font-medium text-sidebar-foreground"
                    title={activeProjectTitle ?? undefined}
                  >
                    {activeProjectTitle}
                  </p>
                  {activeProjectStatusLabel && (
                    <p className="mt-0.5 text-[11px] text-sidebar-foreground/70">
                      Status: {activeProjectStatusLabel}
                    </p>
                  )}
                </>
              ) : (
                <>
                  <p className="text-xs text-sidebar-foreground/60">
                    Kein Antrag ausgewählt
                  </p>
                  <p className="mt-0.5 text-[11px] text-sidebar-foreground/50">
                    In der Projektübersicht einen Antrag wählen.
                  </p>
                </>
              )}
            </div>
            {currentApplication.map((item) =>
              hasProject || PROJECT_INDEPENDENT.has(item.label) ? (
                <ExpandedLink
                  key={item.label}
                  item={item}
                  active={
                    item.href === "/"
                      ? false
                      : pathActive(pathname, item.href)
                  }
                />
              ) : (
                <DisabledRow
                  key={item.label}
                  item={{ label: item.label, icon: item.icon }}
                  hint="Zuerst Antrag auswählen"
                />
              )
            )}
          </>
        )}
      </nav>

      <Tooltip>
        <TooltipTrigger
          render={
            <button
              type="button"
              onClick={onToggle}
              aria-label={toggleLabel}
              aria-controls={navigationId}
              aria-expanded={!collapsed}
              className="absolute bottom-4 right-3 z-20 flex size-9 items-center justify-center rounded-md border border-sidebar-border bg-sidebar text-sidebar-foreground/75 shadow-sm outline-none transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring"
            >
              {collapsed ? (
                <PanelLeftOpen className="size-5 shrink-0" />
              ) : (
                <PanelLeftClose className="size-5 shrink-0" />
              )}
            </button>
          }
        />
        <TooltipContent side="right">{toggleLabel}</TooltipContent>
      </Tooltip>
    </aside>
  )
}

// ---------------------------------------------------------------------------
// Building blocks
// ---------------------------------------------------------------------------
function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="mt-4 px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-sidebar-foreground/50">
      {children}
    </p>
  )
}

function GroupLabel({ children }: { children: ReactNode }) {
  return (
    <p className="px-3 pt-1 text-xs font-medium text-sidebar-foreground/70">
      {children}
    </p>
  )
}

function ExpandedLink({
  item,
  active,
  badge,
}: {
  item: NavLink
  active: boolean
  badge?: string
}) {
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex min-h-[40px] items-center gap-3 rounded-md px-3 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-sidebar-ring",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
      )}
    >
      <item.icon className="size-5 shrink-0" />
      <span className="truncate">{item.label}</span>
      {badge && (
        <span className="ml-auto rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
          {badge}
        </span>
      )}
    </Link>
  )
}

function CollapsedLink({ item, active }: { item: NavLink; active: boolean }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Link
            href={item.href}
            aria-current={active ? "page" : undefined}
            aria-label={item.label}
            className={cn(
              "flex min-h-[44px] items-center justify-center rounded-md outline-none transition-colors focus-visible:ring-2 focus-visible:ring-sidebar-ring",
              active
                ? "bg-sidebar-accent text-sidebar-accent-foreground"
                : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
            )}
          >
            <item.icon className="size-5 shrink-0" />
          </Link>
        }
      />
      <TooltipContent side="right">{item.label}</TooltipContent>
    </Tooltip>
  )
}

function DisabledRow({
  item,
  hint = "Nicht verfügbar",
}: {
  item: DisabledLink
  hint?: string
}) {
  return (
    <div
      aria-disabled="true"
      title={hint}
      className="flex min-h-[40px] cursor-not-allowed items-center gap-3 rounded-md px-3 text-sm font-medium text-sidebar-foreground/35"
    >
      {item.icon && <item.icon className="size-5 shrink-0" />}
      <span className="truncate">{item.label}</span>
      <span className="ml-auto rounded-full border border-sidebar-border px-2 py-0.5 text-[10px] font-medium text-sidebar-foreground/45">
        {hint}
      </span>
    </div>
  )
}

function CollapsedDisabled({ item }: { item: NavLink }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <div
            aria-disabled="true"
            aria-label={`${item.label} — zuerst Antrag auswählen`}
            className="flex min-h-[44px] cursor-not-allowed items-center justify-center rounded-md text-sidebar-foreground/30"
          >
            <item.icon className="size-5 shrink-0" />
          </div>
        }
      />
      <TooltipContent side="right">
        {item.label} — zuerst Antrag auswählen
      </TooltipContent>
    </Tooltip>
  )
}
