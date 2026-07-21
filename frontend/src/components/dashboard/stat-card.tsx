"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  color: string;
  bgColor: string;
  gradient: string;
  trend?: number[]; // last 7 days, small counts for a sparkline row
}

export function StatCard({ label, value, icon: Icon, color, bgColor, gradient, trend }: StatCardProps) {
  const maxTrend = trend && trend.length > 0 ? Math.max(...trend, 1) : 1;

  return (
    <Card className={cn("overflow-hidden border-none shadow-sm bg-gradient-to-br", gradient)}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">{label}</p>
            <p className="text-2xl font-semibold text-gray-900 mt-2">{value}</p>
          </div>
          <div className={cn("w-12 h-12 rounded-lg flex items-center justify-center", bgColor)}>
            <Icon className={cn("w-6 h-6", color)} />
          </div>
        </div>
        {trend && trend.length > 0 && (
          <div className="flex items-end gap-1 mt-4 h-6">
            {trend.map((v, i) => (
              <div
                key={i}
                className={cn("flex-1 rounded-sm", bgColor)}
                style={{ height: `${Math.max((v / maxTrend) * 100, 8)}%`, opacity: 0.4 + (v > 0 ? 0.6 : 0) }}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
