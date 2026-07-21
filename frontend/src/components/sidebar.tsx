"use client";

import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  HardDrive,
  Calendar,
  Archive,
  Users,
  type LucideIcon,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const MENU_ITEMS: { id: string; label: string; icon: LucideIcon; adminOnly?: boolean }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "devices", label: "Devices", icon: HardDrive },
  { id: "backup-schedule", label: "Backup Schedule", icon: Calendar },
  { id: "backups", label: "Backups", icon: Archive },
  { id: "user-settings", label: "User Settings", icon: Users, adminOnly: true },
];

export function Sidebar({
  currentPage,
  onNavigate,
  userRole,
}: {
  currentPage: string;
  onNavigate: (id: string) => void;
  userRole: "admin" | "viewer";
}) {
  return (
    <TooltipProvider delayDuration={100}>
      <aside className="w-16 bg-sidebar text-sidebar-foreground flex flex-col items-center border-r border-sidebar-border">
        <div className="h-14 flex items-center justify-center border-b border-sidebar-border w-full">
          <span className="font-bold text-sm">ABS</span>
        </div>
        <nav className="flex-1 py-4 flex flex-col items-center gap-1">
          {MENU_ITEMS.map((item) => {
            if (item.adminOnly && userRole !== "admin") return null;
            const Icon = item.icon;
            return (
              <Tooltip key={item.id}>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => onNavigate(item.id)}
                    aria-label={item.label}
                    className={cn(
                      "flex items-center justify-center h-10 w-10 rounded-md text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                      currentPage === item.id &&
                        "bg-sidebar-accent text-sidebar-accent-foreground",
                    )}
                  >
                    <Icon className="w-5 h-5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            );
          })}
        </nav>
      </aside>
    </TooltipProvider>
  );
}
