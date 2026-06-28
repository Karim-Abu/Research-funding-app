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
  { label: "Kosten & Laufzeit", href: "/kosten", icon: Wallet },
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
}

function pathActive(pathname: string, href: string): boolean {
  const path = href.split("?")[0]
  if (path === "/") return pathname === "/"
  return pathname === path || pathname.startsWith(`${path}/`)
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname()

  return (
    <aside
      className={cn(
        "flex shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200",
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

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
        {collapsed ? (
          collapsedItems.map((item) => (
            <CollapsedLink
              key={item.label}
              item={item}
              active={pathActive(pathname, item.href)}
            />
          ))
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

            {/* Aktueller Antrag */}
            <SectionLabel>Aktueller Antrag</SectionLabel>
            {currentApplication.map((item) => (
              <ExpandedLink
                key={item.label}
                item={item}
                active={
                  item.href === "/"
                    ? false
                    : pathActive(pathname, item.href)
                }
              />
            ))}
          </>
        )}
      </nav>

      <div className="border-t border-sidebar-border p-2">
        <button
          type="button"
          onClick={onToggle}
          className={cn(
            "flex min-h-[44px] w-full items-center gap-3 rounded-md px-3 text-sm font-medium text-sidebar-foreground/70 outline-none transition-colors hover:bg-sidebar-accent/60 hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring",
            collapsed && "justify-center px-0"
          )}
        >
          {collapsed ? (
            <PanelLeftOpen className="size-5 shrink-0" />
          ) : (
            <PanelLeftClose className="size-5 shrink-0" />
          )}
          {!collapsed && <span>Minimieren</span>}
        </button>
      </div>
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

function DisabledRow({ item }: { item: DisabledLink }) {
  return (
    <div
      aria-disabled="true"
      title="Nicht verfügbar"
      className="flex min-h-[40px] cursor-not-allowed items-center gap-3 rounded-md px-3 text-sm font-medium text-sidebar-foreground/35"
    >
      {item.icon && <item.icon className="size-5 shrink-0" />}
      <span className="truncate">{item.label}</span>
      <span className="ml-auto rounded-full border border-sidebar-border px-2 py-0.5 text-[10px] font-medium text-sidebar-foreground/45">
        Nicht verfügbar
      </span>
    </div>
  )
}
