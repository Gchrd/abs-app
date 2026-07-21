"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, Loader2, CheckCircle2, ArrowRight } from "lucide-react";
import { apiGet } from "@/lib/api";

interface ActiveBackup {
  device_id: number;
  device_name: string;
  status_changed: boolean;
}

export function BackupChangesWidget() {
  const [activeBackups, setActiveBackups] = useState<ActiveBackup[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await apiGet<ActiveBackup[]>("/backups/active");
        if (mounted) setActiveBackups(data);
      } catch {
        // silent — secondary widget
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  const changed = activeBackups.filter((ab) => ab.status_changed);

  return (
    <Card>
      <CardContent className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RefreshCw className="w-4 h-4 text-orange-500 dark:text-orange-400" />
            <h3 className="text-foreground font-semibold">Backup Changes</h3>
          </div>
          {changed.length > 0 && (
            <Badge className="bg-orange-100 text-orange-700 border border-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800">
              {changed.length} changed
            </Badge>
          )}
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
            <Loader2 className="w-4 h-4 animate-spin" /> Checking device configs...
          </div>
        ) : changed.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-400 py-4">
            <CheckCircle2 className="w-4 h-4" /> All device configs match their active reference.
          </div>
        ) : (
          <div className="divide-y divide-border">
            {changed.slice(0, 6).map((ab) => (
              <div key={ab.device_id} className="flex items-center justify-between py-2">
                <span className="text-sm font-medium text-foreground">{ab.device_name}</span>
                <Badge className="bg-orange-100 text-orange-700 border border-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800">
                  🔄 Changed
                </Badge>
              </div>
            ))}
          </div>
        )}

        <Link href="/backups" className="flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline w-fit">
          Review in Backups <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </CardContent>
    </Card>
  );
}
