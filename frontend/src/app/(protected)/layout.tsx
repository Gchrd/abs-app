"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

type User = {
  username: string;
  role: "admin" | "viewer";
} | null;

const pageKeyFromPath = (pathname: string): string => {
  // URL /dashboard -> "dashboard", /devices -> "devices", etc
  const seg = pathname.split("/")[1] || "dashboard";
  return seg;
};

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const [user, setUser] = useState<User>(null);
  const [loading, setLoading] = useState(true);

  // Baca user dari localStorage + guard
  useEffect(() => {
    if (typeof window === "undefined") return;

    const saved = localStorage.getItem("abs_user");
    if (!saved) {
      router.replace("/login");
      return;
    }

    try {
      const parsed = JSON.parse(saved);
      setUser(parsed);
      setLoading(false);
    } catch {
      localStorage.removeItem("abs_user");
      router.replace("/login");
    }
  }, [router]);

  const currentPage = pageKeyFromPath(pathname);

  const handleNavigate = (page: string) => {
    router.push(`/${page}`);
  };

  const handleLogout = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("abs_user");
      localStorage.removeItem("abs_token");
    }
    router.replace("/login");
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-muted-foreground text-sm">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background">
      <Sidebar
        currentPage={currentPage}
        onNavigate={handleNavigate}
        userRole={user?.role || "viewer"}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar
          username={user?.username || ""}
          role={user?.role || "viewer"}
          onLogout={handleLogout}
        />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
