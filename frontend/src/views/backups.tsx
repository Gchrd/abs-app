"use client";

import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Eye, Download, Search, GitCompare, Star, Loader2, ChevronDown, ChevronRight, Trash2, FolderDown } from 'lucide-react';
import { toast } from 'sonner';
import { apiGet, apiGetBlob, apiGetText, apiPut, downloadBackupDate, deleteBackupDate } from '@/lib/api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Backup {
  id: number;
  device_id: number;
  timestamp: string;
  size_bytes: number;
  hash: string;
  status: string;
  device_name?: string;
  content?: string;
}

interface ActiveBackup {
  device_id: number;
  device_name: string;
  backup_id: number;
  timestamp: string;
  size: number;
  hash: string;
  status_changed: boolean;
  previous_backup_id: number | null;
}

interface DiffResult {
  current: string;
  previous: string;
  current_backup_id: number;
  previous_backup_id: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatSize(bytes: number) {
  if (!bytes && bytes !== 0) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(ts: string) {
  if (!ts) return '-';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return d.toLocaleString('id-ID', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ─── Diff Viewer ──────────────────────────────────────────────────────────────

function DiffViewer({ current, previous }: { current: string; previous: string }) {
  const currentLines = current.split('\n');
  const previousLines = previous.split('\n');
  const maxLen = Math.max(currentLines.length, previousLines.length);

  type DiffLine = { type: 'same' | 'added' | 'removed'; text: string; lineNo: number };

  const leftLines: DiffLine[] = [];
  const rightLines: DiffLine[] = [];

  for (let i = 0; i < maxLen; i++) {
    const leftText = i < previousLines.length ? previousLines[i] : '';
    const rightText = i < currentLines.length ? currentLines[i] : '';

    if (leftText === rightText) {
      leftLines.push({ type: 'same', text: leftText, lineNo: i + 1 });
      rightLines.push({ type: 'same', text: rightText, lineNo: i + 1 });
    } else {
      leftLines.push({ type: 'removed', text: leftText, lineNo: i + 1 });
      rightLines.push({ type: 'added', text: rightText, lineNo: i + 1 });
    }
  }

  const bgColor = (type: DiffLine['type']) => {
    if (type === 'added') return 'bg-green-950 text-green-300';
    if (type === 'removed') return 'bg-red-950 text-red-300';
    return 'text-gray-300';
  };

  const lineNumColor = (type: DiffLine['type']) => {
    if (type === 'added') return 'text-green-600';
    if (type === 'removed') return 'text-red-600';
    return 'text-gray-600';
  };

  return (
    <div className="grid grid-cols-2 gap-1 font-mono text-xs overflow-auto max-h-[60vh]">
      {/* Previous (left) */}
      <div className="bg-gray-900 rounded-l overflow-auto">
        <div className="sticky top-0 bg-gray-800 text-gray-400 px-3 py-1 text-xs font-semibold border-b border-gray-700">
          ← Previous
        </div>
        {leftLines.map((line, i) => (
          <div key={i} className={`flex ${bgColor(line.type)}`}>
            <span className={`select-none w-10 shrink-0 text-right pr-3 py-0.5 border-r border-gray-700 ${lineNumColor(line.type)}`}>
              {line.text !== '' ? line.lineNo : ''}
            </span>
            <span className="px-3 py-0.5 whitespace-pre break-all">{line.text}</span>
          </div>
        ))}
      </div>
      {/* Current (right) */}
      <div className="bg-gray-900 rounded-r overflow-auto">
        <div className="sticky top-0 bg-gray-800 text-gray-400 px-3 py-1 text-xs font-semibold border-b border-gray-700">
          Current →
        </div>
        {rightLines.map((line, i) => (
          <div key={i} className={`flex ${bgColor(line.type)}`}>
            <span className={`select-none w-10 shrink-0 text-right pr-3 py-0.5 border-r border-gray-700 ${lineNumColor(line.type)}`}>
              {line.text !== '' ? line.lineNo : ''}
            </span>
            <span className="px-3 py-0.5 whitespace-pre break-all">{line.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function BackupsPage() {
  // Backups
  const [backups, setBackups] = useState<Backup[]>([]);
  const [activeBackups, setActiveBackups] = useState<ActiveBackup[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeLoading, setActiveLoading] = useState(false);

  // Filters
  const [deviceFilter, setDeviceFilter] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');

  // Preview
  const [selectedBackup, setSelectedBackup] = useState<Backup | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [previewingId, setPreviewingId] = useState<number | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  // Set active
  const [settingActiveId, setSettingActiveId] = useState<number | null>(null);

  // Diff modal
  const [isDiffOpen, setIsDiffOpen] = useState(false);
  const [diffData, setDiffData] = useState<DiffResult | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [diffTitle, setDiffTitle] = useState('');
  const [diffActiveBackup, setDiffActiveBackup] = useState<ActiveBackup | null>(null); // konteks diff yang sedang dibuka
  const [revertingId, setRevertingId] = useState<number | null>(null);

  // History Grouping & Batch Actions
  const [expandedDates, setExpandedDates] = useState<Record<string, boolean>>({});
  const [deletingDate, setDeletingDate] = useState<string | null>(null);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [batchActionLoading, setBatchActionLoading] = useState<string | null>(null);

  // Role check
  const u = typeof window !== 'undefined' ? localStorage.getItem('abs_user') : null;
  const user = u ? JSON.parse(u) : null;
  const isAdmin = user?.role === 'admin';

  // ── Fetch ──────────────────────────────────────────────────────────────────

  const fetchBackups = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiGet<unknown[]>('/backups');
      const mapped = data.map((b: unknown) => {
        const backup = b as { id: number; device_id: number; timestamp: string; size: number; hash: string; status: string; device_name?: string };
        return {
          id: backup.id,
          device_id: backup.device_id,
          timestamp: backup.timestamp,
          size_bytes: backup.size,
          hash: backup.hash,
          status: backup.status,
          device_name: backup.device_name ?? String(backup.device_id),
        };
      }) as Backup[];
      setBackups(mapped);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to load backups: ' + (msg || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchActiveBackups = useCallback(async () => {
    setActiveLoading(true);
    try {
      const data = await apiGet<ActiveBackup[]>('/backups/active');
      setActiveBackups(data);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to load active backups: ' + (msg || 'Unknown error'));
    } finally {
      setActiveLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBackups();
    fetchActiveBackups();
  }, [fetchBackups, fetchActiveBackups]);

  // ── Filters ────────────────────────────────────────────────────────────────

  const devices = ['All', ...Array.from(new Set(backups.map(b => b.device_name ?? String(b.device_id))))];

  const filteredBackups = backups.filter(backup => {
    const name = backup.device_name ?? String(backup.device_id);
    const matchesDevice = deviceFilter === 'All' || name === deviceFilter;
    const matchesSearch = searchQuery === '' ||
      name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      backup.timestamp.includes(searchQuery);
    return matchesDevice && matchesSearch;
  });

  // ── Handlers ───────────────────────────────────────────────────────────────

  const handlePreview = async (backup: Backup) => {
    setPreviewingId(backup.id);
    try {
      const txt = await apiGetText(`/backups/${backup.id}/download`);
      setSelectedBackup({ ...backup, content: txt });
      setIsPreviewOpen(true);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to load backup preview: ' + (msg || 'Unknown error'));
    } finally {
      setPreviewingId(null);
    }
  };

  const handleDownload = async (backup: Backup) => {
    setDownloadingId(backup.id);
    try {
      const blob = await apiGetBlob(`/backups/${backup.id}/download`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${backup.device_name ?? backup.device_id}_${backup.timestamp.replace(/[: ]/g, '-')}.cfg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('Backup file downloaded successfully');
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to download backup: ' + (msg || 'Unknown error'));
    } finally {
      setDownloadingId(null);
    }
  };

  const handleSetActive = async (backupId: number) => {
    setSettingActiveId(backupId);
    try {
      await apiPut(`/backups/${backupId}/set-active`, {});
      await Promise.all([fetchBackups(), fetchActiveBackups()]);
      toast.success('Active backup updated.');
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to set active backup: ' + (msg || 'Unknown error'));
    } finally {
      setSettingActiveId(null);
    }
  };

  // Sets the LATEST backup (right panel) as active
  const handleAcceptLatest = async () => {
    if (!diffActiveBackup?.previous_backup_id) return;
    setRevertingId(diffActiveBackup.previous_backup_id);
    try {
      await apiPut(`/backups/${diffActiveBackup.previous_backup_id}/set-active`, {});
      await Promise.all([fetchBackups(), fetchActiveBackups()]);
      toast.success(`Active backup for ${diffActiveBackup.device_name} set to latest.`);
      setIsDiffOpen(false);
      setDiffActiveBackup(null);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to update active backup: ' + (msg || 'Unknown error'));
    } finally {
      setRevertingId(null);
    }
  };

  // Sets the CURRENT REFERENCE backup (left panel) as active explicitly, AND acknowledges the latest (right panel)
  const handleKeepPrevious = async () => {
    if (!diffActiveBackup?.backup_id) return;
    setRevertingId(diffActiveBackup.backup_id);
    try {
      // 1. Re-affirm the old backup as active
      await apiPut(`/backups/${diffActiveBackup.backup_id}/set-active`, {});
      // 2. Acknowledge the latest backup so 'Changed' alert is cleared
      if (diffActiveBackup.previous_backup_id) {
        await apiPut(`/backups/${diffActiveBackup.previous_backup_id}/acknowledge`, {});
      }
      await Promise.all([fetchBackups(), fetchActiveBackups()]);
      toast.success(`Previous config retained for ${diffActiveBackup.device_name}.`);
      setIsDiffOpen(false);
      setDiffActiveBackup(null);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to update active backup: ' + (msg || 'Unknown error'));
    } finally {
      setRevertingId(null);
    }
  };

  const handleViewDiff = async (active: ActiveBackup) => {
    if (!active.previous_backup_id) return;
    setDiffTitle(`${active.device_name} — Config Diff`);
    setDiffActiveBackup(active);
    setIsDiffOpen(true);
    setDiffLoading(true);
    try {
      const data = await apiGet<DiffResult>(
        // previous_backup_id is now the NEWER backup; flip so diff shows reference (left) vs latest (right)
        `/backups/diff?current=${active.previous_backup_id}&previous=${active.backup_id}`
      );
      setDiffData(data);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to load diff: ' + (msg || 'Unknown error'));
      setIsDiffOpen(false);
    } finally {
      setDiffLoading(false);
    }
  };

  const toggleDate = (date: string) => {
    setExpandedDates(prev => ({ ...prev, [date]: !prev[date] }));
  };

  const handleDownloadDate = async (date: string) => {
    setBatchActionLoading(`download-${date}`);
    try {
      const blob = await downloadBackupDate(date);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `backups_${date}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(`Successfully downloaded backup folder for ${date}`);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to download folder: ' + (msg || 'Unknown error'));
    } finally {
      setBatchActionLoading(null);
    }
  };

  const handleDeleteDate = async () => {
    if (!deletingDate) return;
    setBatchActionLoading(`delete-${deletingDate}`);
    try {
      await deleteBackupDate(deletingDate);
      toast.success(`Successfully deleted backup folder for ${deletingDate}`);
      setDeletingDate(null);
      setDeleteConfirmText('');
      fetchBackups(); // Refresh data
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to delete folder: ' + (msg || 'Unknown error'));
    } finally {
      setBatchActionLoading(null);
    }
  };

  // Group filteredBackups by Date (YYYY-MM-DD from local timezone)
  const groupedBackups = filteredBackups.reduce((groups: Record<string, Backup[]>, backup) => {
    const d = new Date(backup.timestamp);
    // Use local timezone formatting for grouping to avoid UTC shift
    // padStart handles single digit months/days natively
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const dateKey = `${yyyy}-${mm}-${dd}`;
    if (!groups[dateKey]) groups[dateKey] = [];
    groups[dateKey].push(backup);
    return groups;
  }, {});

  // Sort dates descending
  const sortedDates = Object.keys(groupedBackups).sort((a, b) => b.localeCompare(a));

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-gray-900">Backups</h2>
        <p className="text-gray-500">Browse and manage backup configurations</p>
      </div>

      {/* ── Tabel 1: Active Backups ── */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Star className="w-4 h-4 text-amber-500" />
          <h3 className="text-base font-semibold text-gray-800">Active Backup</h3>
          <span className="text-xs text-gray-500">(1 per device — config's references)</span>
        </div>

        <div className="border rounded-lg bg-white">
          {activeLoading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="w-6 h-6 animate-spin text-blue-500 mr-2" />
              <span className="text-gray-500 text-sm">Loading active backups...</span>
            </div>
          ) : activeBackups.length === 0 ? (
            <div className="flex items-center justify-center py-10">
              <p className="text-gray-400 text-sm"> Inactive backup</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Device</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Hash</TableHead>
                  <TableHead>Config Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeBackups.map((ab) => (
                  <TableRow key={ab.device_id}>
                    <TableCell className="font-medium">{ab.device_name}</TableCell>
                    <TableCell className="text-sm">{formatDate(ab.timestamp)}</TableCell>
                    <TableCell>{formatSize(ab.size)}</TableCell>
                    <TableCell>
                      <code className="text-xs bg-gray-100 px-2 py-1 rounded">{ab.hash.slice(0, 8)}</code>
                    </TableCell>
                    <TableCell>
                      {ab.status_changed ? (
                        <Badge className="bg-orange-100 text-orange-700 border border-orange-200">
                          🔄 Changed
                        </Badge>
                      ) : (
                        <Badge className="bg-green-100 text-green-700 border border-green-200">
                          ✅ Unchanged
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            const backup = backups.find(b => b.id === ab.backup_id);
                            if (backup) handlePreview(backup);
                          }}
                          className="gap-1"
                        >
                          <Eye className="w-3 h-3" />
                          View
                        </Button>
                        {ab.status_changed && ab.previous_backup_id && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleViewDiff(ab)}
                            className="gap-1 text-orange-600 border-orange-300 hover:bg-orange-50"
                          >
                            <GitCompare className="w-3 h-3" />
                            View Diff
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </div>

      {/* ── Filters for History Table ── */}
      <div className="flex gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Device:</span>
          <Select value={deviceFilter} onValueChange={setDeviceFilter}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {devices.map(device => (
                <SelectItem key={device} value={device}>{device}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Date Range:</span>
          <Input type="date" className="w-48" />
          <span className="text-sm text-gray-600">to</span>
          <Input type="date" className="w-48" />
        </div>

        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            placeholder="Search backups..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Retention Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-800">
          💡 Retention policy automatically keeps the last N backups per device based on schedule settings. Old backups are pruned after successful new backups.
        </p>
      </div>

      {/* ── Tabel 2: Backup History ── */}
      <div className="space-y-3">
        <h3 className="text-base font-semibold text-gray-800">Backup History</h3>
        <div className="bg-white rounded-lg">
          {loading && backups.length === 0 ? (
            <div className="flex items-center justify-center py-12 border rounded-lg">
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
                <p className="text-gray-500">Loading backups...</p>
              </div>
            </div>
          ) : sortedDates.length === 0 ? (
            <div className="flex items-center justify-center py-12 border rounded-lg">
              <p className="text-gray-500">No backups found</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {sortedDates.map((dateKey) => {
                const dayBackups = groupedBackups[dateKey];
                const isExpanded = expandedDates[dateKey] || false;
                // Cek apakah ada yg active
                const hasActiveBackup = dayBackups.some(b => activeBackups.some(ab => ab.backup_id === b.id));
                const d = new Date(dateKey);
                const displayDate = d.toLocaleDateString('id-ID', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

                return (
                  <div key={dateKey} className="border rounded-lg overflow-hidden bg-white shadow-sm">
                    {/* Header bar */}
                    <div
                      className={`flex items-center justify-between p-3 cursor-pointer ${isExpanded ? 'bg-gray-50 border-b' : 'hover:bg-gray-50'}`}
                      onClick={() => toggleDate(dateKey)}
                    >
                      <div className="flex items-center gap-3 flex-1">
                        <span className="text-gray-400">
                          {isExpanded ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                        </span>
                        <div className="flex flex-col">
                          <span className="font-semibold text-gray-800">{displayDate}</span>
                          <span className="text-xs text-gray-500">{dayBackups.length} backup file{dayBackups.length > 1 ? 's' : ''}</span>
                        </div>
                        {hasActiveBackup && (
                          <Badge variant="outline" className="ml-2 bg-amber-50 text-amber-700 border-amber-200">
                            <Star className="w-3 h-3 fill-amber-500 text-amber-500 mr-1" />
                            Active Backup Present
                          </Badge>
                        )}
                      </div>

                      {/* Batch Actions */}
                      <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="outline"
                          size="sm"
                          className="gap-2"
                          disabled={batchActionLoading === `download-${dateKey}`}
                          onClick={() => handleDownloadDate(dateKey)}
                        >
                          {batchActionLoading === `download-${dateKey}` ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <FolderDown className="w-4 h-4 text-blue-600" />
                          )}
                          <span className="hidden sm:inline">Download Folder</span>
                        </Button>

                        {!hasActiveBackup && isAdmin && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="gap-2 text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
                            onClick={() => setDeletingDate(dateKey)}
                          >
                            <Trash2 className="w-4 h-4" />
                            <span className="hidden sm:inline">Delete Folder</span>
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* Expanded Content */}
                    {isExpanded && (
                      <div className="bg-white p-2">
                        <Table>
                          <TableHeader className="bg-gray-50">
                            <TableRow>
                              <TableHead className="w-12 text-center text-xs">#</TableHead>
                              <TableHead className="text-xs">Device</TableHead>
                              <TableHead className="text-xs">Time</TableHead>
                              <TableHead className="text-xs">Size</TableHead>
                              <TableHead className="text-xs">Hash</TableHead>
                              <TableHead className="text-xs">Status</TableHead>
                              <TableHead className="text-xs">Actions</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {dayBackups.map((backup, idx) => {
                              const isCurrentlyActive = activeBackups.some(ab => ab.backup_id === backup.id);
                              const isSuccess = backup.status === 'success';
                              return (
                                <TableRow key={backup.id} className={isCurrentlyActive ? 'bg-amber-50/50' : ''}>
                                  <TableCell className="text-xs text-gray-400 text-center">{idx + 1}</TableCell>
                                  <TableCell>
                                    <div className="flex items-center gap-1.5 font-medium">
                                      {backup.device_name ?? String(backup.device_id)}
                                      {isCurrentlyActive && (
                                        <Star className="w-3 h-3 text-amber-500 fill-amber-500" aria-label="Active Backup" />
                                      )}
                                    </div>
                                  </TableCell>
                                  <TableCell className="text-sm">
                                    {new Date(backup.timestamp).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}
                                  </TableCell>
                                  <TableCell className="text-sm text-gray-600">{formatSize(backup.size_bytes)}</TableCell>
                                  <TableCell>
                                    <code className="text-xs bg-gray-100/80 px-1.5 py-0.5 rounded text-gray-500">{backup.hash.slice(0, 8)}</code>
                                  </TableCell>
                                  <TableCell>
                                    {isSuccess ? (
                                      <Badge className="bg-green-100/70 text-green-700 text-[10px] px-1.5 border border-green-200">✅ success</Badge>
                                    ) : (
                                      <Badge className="bg-red-100/70 text-red-700 text-[10px] px-1.5 border border-red-200">❌ failed</Badge>
                                    )}
                                  </TableCell>
                                  <TableCell>
                                    {isSuccess ? (
                                      <div className="flex gap-2">
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={() => handlePreview(backup)}
                                          title="Preview"
                                          className="h-8 w-8 p-0"
                                          disabled={previewingId === backup.id || downloadingId === backup.id}
                                        >
                                          {previewingId === backup.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4 text-gray-500" />}
                                        </Button>
                                        {!isCurrentlyActive && isAdmin && (
                                          <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => handleSetActive(backup.id)}
                                            title="Jadikan Active Backup"
                                            className="h-8 w-8 p-0"
                                            disabled={settingActiveId === backup.id}
                                          >
                                            {settingActiveId === backup.id ? <Loader2 className="w-4 h-4 animate-spin text-amber-500" /> : <Star className="w-4 h-4 text-gray-400 hover:text-amber-500" />}
                                          </Button>
                                        )}
                                      </div>
                                    ) : (
                                      <span className="text-xs text-gray-400">-</span>
                                    )}
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Preview Modal ── */}
      <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
        <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>
              {selectedBackup?.device_name ?? selectedBackup?.device_id} — {formatDate(selectedBackup?.timestamp ?? '')}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-hidden py-2">
            <div className="bg-gray-900 text-gray-100 p-4 rounded-lg h-full overflow-auto font-mono text-sm">
              <pre className="whitespace-pre-wrap break-words">{selectedBackup?.content}</pre>
            </div>
          </div>
          <DialogFooter className="mt-4">
            <Button
              variant="outline"
              onClick={() => selectedBackup && handleDownload(selectedBackup)}
              className="gap-2"
              disabled={downloadingId === selectedBackup?.id}
            >
              {downloadingId === selectedBackup?.id ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Downloading...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  Download
                </>
              )}
            </Button>
            <Button onClick={() => setIsPreviewOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Diff Modal ── */}
      <Dialog open={isDiffOpen} onOpenChange={setIsDiffOpen}>
        <DialogContent className="max-w-5xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <GitCompare className="w-4 h-4 text-orange-500" />
              {diffTitle}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-hidden py-2">
            {diffLoading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500 mr-3" />
                <span className="text-gray-500">Loading diff...</span>
              </div>
            ) : diffData ? (
              <>
                <div className="mb-2 flex gap-4 text-xs text-gray-500">
                  <span>
                    <span className="inline-block w-3 h-3 bg-red-900 rounded mr-1"></span>
                    Removed / Previous
                  </span>
                  <span>
                    <span className="inline-block w-3 h-3 bg-green-900 rounded mr-1"></span>
                    Added / Current
                  </span>
                </div>
                <DiffViewer current={diffData.current} previous={diffData.previous} />
              </>
            ) : null}
          </div>
          <DialogFooter className="mt-4 border-t pt-4">
            <div className="flex items-center justify-between w-full gap-3">
              {/* Dismiss without choosing */}
              <Button
                variant="ghost"
                size="sm"
                className="text-gray-400 hover:text-gray-600"
                onClick={() => {
                  setIsDiffOpen(false);
                  setDiffActiveBackup(null);
                }}
                disabled={revertingId !== null}
              >
                Cancel
              </Button>

              {/* Two explicit choices */ isAdmin && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={handleKeepPrevious}
                    disabled={revertingId !== null}
                    className="font-medium"
                  >
                    {revertingId === diffActiveBackup?.backup_id ? (
                      <><Loader2 className="w-4 h-4 animate-spin mr-1" /> Setting...</>
                    ) : (
                      'Use Previous Config'
                    )}
                  </Button>
                  {diffActiveBackup?.previous_backup_id && (
                    <Button
                      variant="outline"
                      onClick={handleAcceptLatest}
                      disabled={revertingId !== null}
                      className="text-blue-600 border-blue-300 hover:bg-blue-50 font-medium"
                    >
                      {revertingId === diffActiveBackup?.previous_backup_id ? (
                        <><Loader2 className="w-4 h-4 animate-spin mr-1" /> Setting...</>
                      ) : (
                        'Use Latest Config'
                      )}
                    </Button>
                  )}
                </div>
              )}
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog Konfirmasi Delete Folder ── */}
      <Dialog open={deletingDate !== null} onOpenChange={(open) => !open && setDeletingDate(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <Trash2 className="w-5 h-5" />
              Confirm Delete Permanently
            </DialogTitle>
          </DialogHeader>
          <div className="py-4 space-y-4">
            <p className="text-sm text-gray-600">
              You are about to permanently delete all backup configuration files on <strong>{deletingDate && new Date(deletingDate).toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</strong>.
            </p>
            <div className="bg-red-50 border border-red-200 text-red-800 p-3 rounded text-sm">
              <p className="font-semibold mb-1">Warning!</p>
              <ul className="list-disc pl-5 space-y-1">
                <li>This action cannot be undone.</li>
                <li>All history and physical config files in the database and server for today will be deleted.</li>
              </ul>
            </div>
            <div className="space-y-2 pt-2">
              <label className="text-sm font-medium text-gray-700">
                Type <span className="font-bold text-black select-none">I am sure</span> to continue:
              </label>
              <Input
                placeholder="Type 'I am sure' to continue"
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setDeletingDate(null); setDeleteConfirmText(''); }}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={deleteConfirmText !== "I am sure" || batchActionLoading === `delete-${deletingDate}`}
              onClick={handleDeleteDate}
              className="gap-2"
            >
              {batchActionLoading === `delete-${deletingDate}` ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Deleting...</>
              ) : (
                <><Trash2 className="w-4 h-4" /> Yes, Delete Permanently</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}