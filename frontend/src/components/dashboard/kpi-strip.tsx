"use client";

import { Card } from "@/components/ui/card";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface KpiItem {
  label: string;
  value: string;
  icon: LucideIcon;
  colorClass: string;
}

export function KpiStrip({ items }: { items: KpiItem[] }) {
  return (
    <Card className="p-0 gap-0">
      <div className="grid grid-cols-2 sm:grid-cols-4 divide-y sm:divide-y-0 divide-x-0 sm:divide-x divide-border">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="flex items-center gap-3 px-5 py-4">
              <Icon className={cn("w-5 h-5 shrink-0", item.colorClass)} />
              <div className="min-w-0">
                <p className={cn("text-xl font-bold leading-none", item.colorClass)}>{item.value}</p>
                <p className="text-xs text-muted-foreground mt-1 truncate">{item.label}</p>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
