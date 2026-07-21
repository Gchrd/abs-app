"use client";

import { Button } from "./ui/button";
import { ThemeToggle } from "./theme-toggle";

export function Topbar({
  username,
  role,
  onLogout,
}: {
  username: string;
  role: "admin" | "viewer";
  onLogout: () => void;
}) {
  return (
    <header className="h-14 border-b bg-card flex items-center justify-between px-4">
      <div className="font-semibold text-sm text-foreground">
        Automated Backup System
      </div>
      <div className="flex items-center gap-3 text-sm">
        <span className="text-muted-foreground">
          {username} ({role})
        </span>
        <ThemeToggle />
        <Button variant="outline" size="sm" onClick={onLogout}>
          Logout
        </Button>
      </div>
    </header>
  );
}
