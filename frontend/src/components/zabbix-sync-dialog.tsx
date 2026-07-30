"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Loader2, RadioTower, Plus } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost } from "@/lib/api";

interface HostGroup {
  groupid: string;
  name: string;
}

interface Candidate {
  hostname: string;
  ip: string;
  open_ports: number[];
}

export function ZabbixSyncDialog({
  open,
  onOpenChange,
  onPick,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (candidate: { hostname: string; ip: string }) => void;
}) {
  const [groups, setGroups] = useState<HostGroup[]>([]);
  const [loadingGroups, setLoadingGroups] = useState(false);
  const [selectedGroupIds, setSelectedGroupIds] = useState<Set<string>>(new Set());
  const [checking, setChecking] = useState(false);
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);

  useEffect(() => {
    if (!open) return;
    setCandidates(null);
    setSelectedGroupIds(new Set());
    setLoadingGroups(true);
    apiGet<HostGroup[]>("/zabbix/host-groups")
      .then(setGroups)
      .catch((err: unknown) => {
        const msg = (err && typeof err === "object" && "message" in err) ? (err as { message?: string }).message : String(err);
        toast.error("Failed to load Zabbix host groups: " + (msg || "Unknown error"));
      })
      .finally(() => setLoadingGroups(false));
  }, [open]);

  const toggleGroup = (id: string) => {
    setSelectedGroupIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleCheck = async () => {
    if (selectedGroupIds.size === 0) {
      toast.error("Pick at least one host group first");
      return;
    }
    setChecking(true);
    setCandidates(null);
    try {
      const res = await apiPost<{ group_ids: string[] }, { candidates: Candidate[] }>(
        "/zabbix/sync",
        { group_ids: Array.from(selectedGroupIds) }
      );
      setCandidates(res.candidates);
    } catch (err: unknown) {
      const msg = (err && typeof err === "object" && "message" in err) ? (err as { message?: string }).message : String(err);
      toast.error("Zabbix sync failed: " + (msg || "Unknown error"));
    } finally {
      setChecking(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RadioTower className="w-4 h-4" /> Sync from Zabbix
          </DialogTitle>
          <DialogDescription>
            Pick host group(s) to check. Only devices not already in ABS, and that respond on port 22/23, will be shown.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2">
          {loadingGroups ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading host groups...
            </div>
          ) : (
            <div className="space-y-2 max-h-40 overflow-y-auto border rounded-md p-3">
              {groups.map((g) => (
                <label key={g.groupid} className="flex items-center gap-2 text-sm cursor-pointer">
                  <Checkbox
                    checked={selectedGroupIds.has(g.groupid)}
                    onCheckedChange={() => toggleGroup(g.groupid)}
                  />
                  {g.name}
                </label>
              ))}
              {groups.length === 0 && (
                <p className="text-sm text-muted-foreground">No host groups found.</p>
              )}
            </div>
          )}

          <Button onClick={handleCheck} disabled={checking || loadingGroups} className="gap-2">
            {checking ? <Loader2 className="w-4 h-4 animate-spin" /> : <RadioTower className="w-4 h-4" />}
            Check
          </Button>

          {candidates !== null && (
            <div className="space-y-2 pt-2 border-t">
              {candidates.length === 0 ? (
                <p className="text-sm text-muted-foreground py-2">
                  No new reachable devices found in the selected group(s).
                </p>
              ) : (
                candidates.map((c) => (
                  <div key={c.ip} className="flex items-center justify-between border rounded-md p-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{c.hostname}</p>
                      <p className="text-xs text-muted-foreground">
                        {c.ip} · port {c.open_ports.join(", ")}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1 shrink-0"
                      onClick={() => {
                        onPick({ hostname: c.hostname, ip: c.ip });
                        onOpenChange(false);
                      }}
                    >
                      <Plus className="w-3.5 h-3.5" /> Add
                    </Button>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
