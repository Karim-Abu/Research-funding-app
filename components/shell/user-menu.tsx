"use client"

import { useRouter } from "next/navigation"
import { ChevronDown, User as UserIcon, LogOut } from "lucide-react"
import { useSession } from "@/components/providers/app-providers"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { User } from "@/lib/types"

function initials(name: string) {
  return name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase()
}

export function UserMenu({ user }: { user: User }) {
  const router = useRouter()
  const { logout } = useSession()

  async function handleLogout() {
    await logout()
    router.push("/login")
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex min-h-[44px] items-center gap-2 rounded-md px-2 outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring">
        <Avatar className="size-8">
          <AvatarFallback className="bg-primary/15 text-xs font-semibold text-primary">
            {initials(user.name)}
          </AvatarFallback>
        </Avatar>
        <span className="flex flex-col items-start leading-tight">
          <span className="text-sm font-medium text-foreground">
            {user.name}
          </span>
          <span className="text-xs text-muted-foreground">
            {user.displayRole}
          </span>
        </span>
        <ChevronDown className="size-4 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuGroup>
          <DropdownMenuItem>
            <UserIcon className="size-4" />
            Profil
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={handleLogout}>
            <LogOut className="size-4" />
            Abmelden
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
