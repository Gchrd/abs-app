"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search, Download, Loader2, FileSearch, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiGetBlob } from "@/lib/api";

interface Backup {
  id: number;
  device_id: number;
  timestamp: string;
  size: number;
  hash: string;
  status: string;
  device_name?: string;
}

function formatDate(ts: string) {
  if (!ts) return "-";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return d.toLocaleString("id-ID", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function QuickSearchDownload() {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await apiGet<Backup[]>("/backups");
        if (mounted) setBackups(data);
      } catch {
        // silent — this is a secondary widget, the main dashboard fetches already surface errors
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  const handleDownload = useCallback(async (backup: Backup) => {
    setDownloadingId(backup.id);
    try {
      const blob = await apiGetBlob(`/backups/${backup.id}/download`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${backup.device_name ?? backup.device_id}_${backup.timestamp.replace(/[: ]/g, "-")}.cfg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("Backup file downloaded successfully");
    } catch (err: unknown) {
      const msg = (err && typeof err === "object" && "message" in err) ? (err as { message?: string }).message : String(err);
      toast.error("Failed to download backup: " + (msg || "Unknown error"));
    } finally {
      setDownloadingId(null);
    }
  }, []);

  const matches = query.trim() === ""
    ? []
    : backups.filter((b) => {
        const name = b.device_name ?? String(b.device_id);
        return name.toLowerCase().includes(query.toLowerCase()) || b.timestamp.includes(query);
      }).slice(0, 8);

  return (
    <Card>
      <CardContent className="p-6 space-y-4">
        <div className="flex items-center gap-2">
          <FileSearch className="w-4 h-4 text-blue-600" />
          <h3 className="text-gray-900 font-semibold">Quick Search & Download</h3>
        </div>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            placeholder="Search by device or date..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-10"
            disabled={loading}
          />
        </div>

        <div className="min-h-[3rem]">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-gray-400 py-4">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading backups...
            </div>
          ) : query.trim() === "" ? (
            <p className="text-sm text-gray-400 py-4">Type a device name or date to find a backup to download.</p>
          ) : matches.length === 0 ? (
            <p className="text-sm text-gray-400 py-4">No backups match &quot;{query}&quot;.</p>
          ) : (
            <div className="divide-y">
              {matches.map((b) => (
                <div key={b.id} className="flex items-center justify-between py-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{b.device_name ?? b.device_id}</p>
                    <p className="text-xs text-gray-500">{formatDate(b.timestamp)}</p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1 shrink-0"
                    disabled={downloadingId === b.id}
                    onClick={() => handleDownload(b)}
                  >
                    {downloadingId === b.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5" />
                    )}
                    Download
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <Link href="/backups" className="flex items-center gap-1 text-sm text-blue-600 hover:underline w-fit">
          View all backups <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </CardContent>
    </Card>
  );
}
