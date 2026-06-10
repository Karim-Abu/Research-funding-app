"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  FileText,
  Database,
  CheckSquare,
  Download,
  Wallet,
  Users,
  Settings,
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

interface NavItem {
  label: string
  href: string
  icon: LucideIcon
  /** Only rendered for this role. */
  requiredRole?: Role
}

const navItems: NavItem[] = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Anträge", href: "/antraege", icon: FileText },
  { label: "Quellen & Evidenz", href: "/quellen", icon: Database },
  { label: "Review", href: "/review", icon: CheckSquare },
  { label: "Export", href: "/export", icon: Download },
  { label: "Kosten & Laufzeit", href: "/kosten", icon: Wallet },
  { label: "Partner & Rollen", href: "/partner", icon: Users },
  { label: "Admin", href: "/admin", icon: Settings, requiredRole: "lead_admin" },
]

interface SidebarProps {
  role: Role
  collapsed: boolean
  onToggle: () => void
}

export function Sidebar({ role, collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname()
  // Conditionally build the list so role-gated items never reach the DOM.
  const items = navItems.filter(
    (item) => !item.requiredRole || item.requiredRole === role
  )

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
          <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
            EP
          </span>
          {!collapsed && (
            <span className="text-sm font-semibold leading-tight text-sidebar-foreground">
              Proposal-
              <br />
              Unterstützung
            </span>
          )}
        </Link>
      </div>

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
        {items.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href)
          const link = (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex min-h-[44px] items-center gap-3 rounded-md px-3 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-sidebar-ring",
                collapsed && "justify-center px-0",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
              )}
            >
              <item.icon className="size-5 shrink-0" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          )

          if (collapsed) {
            return (
              <Tooltip key={item.href}>
                <TooltipTrigger render={link} />
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            )
          }
          return link
        })}
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
