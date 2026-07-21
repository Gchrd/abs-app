"use client";

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Plus, Edit, Trash2, CheckCircle, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { apiGet, apiPost, apiPut, apiDelete } from '@/lib/api';

interface Schedule {
  id: number;
  name: string;
  interval_days?: number;
  intervalDays?: number;
  run_at?: string;
  runAt?: string;
  target_type?: string;
  targetType?: string;
  target_tags?: string;
  targetTags?: string;
  retention?: number;
  notify_on_fail?: boolean;
  notifyOnFail?: boolean;
  enabled: boolean;
}

export function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [availableTags, setAvailableTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    intervalDays: 7,
    runAt: '02:00',
    targetType: 'All',
    targetTags: '',
    retention: 10,
    notifyOnFail: true,
    enabled: true,
  });

  const [userRole] = useState<'admin' | 'viewer'>(() => {
    try {
      if (typeof window === 'undefined') return 'viewer';
      const u = localStorage.getItem('abs_user');
      if (!u) return 'viewer';
      return JSON.parse(u).role as 'admin' | 'viewer';
    } catch {
      return 'viewer';
    }
  });

  const fetchSchedules = async () => {
    setLoading(true);
    try {
      const data = await apiGet<Schedule[]>('/schedules');
      setSchedules(data);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to load schedules: ' + (msg || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  const fetchAvailableTags = async () => {
    try {
      const data = await apiGet<{ tags: string[] }>('/devices/tags/available');
      setAvailableTags(data.tags || []);
    } catch (err) {
      console.error('Failed to load tags:', err);
    }
  };

  useEffect(() => {
    fetchSchedules();
    fetchAvailableTags();
  }, []);

  const handleAddSchedule = () => {
    setEditingSchedule(null);
    setFormData({
      name: '',
      intervalDays: 7,
      runAt: '02:00',
      targetType: 'All',
      targetTags: '',
      retention: 10,
      notifyOnFail: true,
      enabled: true,
    });
    setIsDialogOpen(true);
  };

  const handleEditSchedule = (schedule: Schedule) => {
    setEditingSchedule(schedule);
    setFormData({
      name: schedule.name,
      intervalDays: schedule.interval_days ?? schedule.intervalDays ?? 7,
      runAt: schedule.run_at ?? schedule.runAt ?? '02:00',
      targetType: schedule.target_type ?? schedule.targetType ?? 'All',
      targetTags: schedule.target_tags ?? schedule.targetTags ?? '',
      retention: schedule.retention ?? 10,
      notifyOnFail: schedule.notify_on_fail ?? schedule.notifyOnFail ?? true,
      enabled: schedule.enabled,
    });
    setIsDialogOpen(true);
  };

  const handleSaveSchedule = async () => {
    if (!formData.name) {
      toast.error('Please enter a schedule name');
      return;
    }

    if (formData.intervalDays < 1) {
      toast.error('Interval must be at least 1 day');
      return;
    }

    if (formData.targetType === 'Tag' && !formData.targetTags) {
      toast.error('Please select at least one tag');
      return;
    }

    setSavingSchedule(true);
    try {
      const payload = {
        name: formData.name,
        schedule_time: formData.runAt,
        enabled: formData.enabled,
        interval_days: formData.intervalDays,
        target_type: formData.targetType,
        target_tags: formData.targetType === 'Tag' ? formData.targetTags : null,
      };

      if (editingSchedule) {
        await apiPut(`/schedules/${editingSchedule.id}`, payload);
        toast.success('Schedule updated successfully');
      } else {
        await apiPost('/schedules', payload);
        toast.success('Schedule created successfully');
      }
      await fetchSchedules();
      setIsDialogOpen(false);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to save schedule: ' + (msg || 'Unknown error'));
    } finally {
      setSavingSchedule(false);
    }
  };

  const handleDeleteSchedule = async (id: number) => {
    if (!confirm('Are you sure you want to delete this schedule?')) {
      return;
    }

    setDeletingId(id);
    try {
      await apiDelete(`/schedules/${id}`);
      toast.success('Schedule deleted successfully');
      await fetchSchedules();
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to delete schedule: ' + (msg || 'Unknown error'));
    } finally {
      setDeletingId(null);
    }
  };

  const handleToggleEnabled = async (schedule: Schedule) => {
    setTogglingId(schedule.id);
    try {
      const newEnabledState = !schedule.enabled;
      await apiPut(`/schedules/${schedule.id}`, {
        name: schedule.name,
        schedule_time: schedule.run_at ?? schedule.runAt ?? '02:00',
        enabled: newEnabledState,
        interval_days: schedule.interval_days ?? schedule.intervalDays ?? 7,
        target_type: schedule.target_type ?? schedule.targetType,
        target_tags: schedule.target_tags ?? schedule.targetTags,
      });
      toast.success(`Schedule ${newEnabledState ? 'enabled' : 'disabled'}`);
      await fetchSchedules();
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to toggle schedule: ' + (msg || 'Unknown error'));
    } finally {
      setTogglingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-foreground">Schedules</h2>
          <p className="text-muted-foreground">Automated backup schedules (Asia/Jakarta timezone)</p>
        </div>
        {userRole === 'admin' && (
          <Button onClick={handleAddSchedule} className="gap-2" disabled={loading}>
            <Plus className="w-4 h-4" />
            Add Schedule
          </Button>
        )}
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 dark:bg-blue-950 dark:border-blue-900 rounded-lg p-4">
        <p className="text-blue-800 dark:text-blue-300 text-sm mb-2">
          📅 <strong>How scheduling works:</strong>
        </p>
        <ul className="text-blue-700 dark:text-blue-300 text-sm space-y-1 ml-6 list-disc">
          <li>Schedules trigger backup jobs automatically at specified intervals</li>
          <li>Only <strong>enabled devices</strong> will be backed up</li>
          <li>Jobs run in the background and can be monitored in the Jobs page</li>
          <li>Disable a schedule to stop automatic backups without deleting it</li>
        </ul>
      </div>

      {/* Schedules Table */}
      <div className="border rounded-lg bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Interval (days)</TableHead>
              <TableHead>Run At</TableHead>
              <TableHead>Target</TableHead>
              <TableHead>Retention</TableHead>
              <TableHead>Enabled</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {schedules.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  {loading ? 'Loading schedules...' : 'No schedules found'}
                </TableCell>
              </TableRow>
            ) : (
              schedules.map((schedule) => {
                const intervalDays = schedule.interval_days ?? schedule.intervalDays ?? 0;
                const runAt = schedule.run_at ?? schedule.runAt ?? '';
                const targetType = schedule.target_type ?? schedule.targetType ?? 'All';
                const targetTags = schedule.target_tags ?? schedule.targetTags ?? '';
                const retention = schedule.retention ?? 10;
                
                // Format target display
                let targetDisplay = targetType;
                if (targetType === 'Tag' && targetTags) {
                  targetDisplay = `Tag: ${targetTags}`;
                }
                
                return (
                  <TableRow key={schedule.id}>
                    <TableCell>{schedule.name}</TableCell>
                    <TableCell>{intervalDays}</TableCell>
                    <TableCell>{runAt}</TableCell>
                    <TableCell>{targetDisplay}</TableCell>
                    <TableCell>Keep {retention}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Badge className={schedule.enabled ? 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300' : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'}>
                          {schedule.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        {userRole === 'admin' ? (
                          <>
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => handleEditSchedule(schedule)}
                              title="Edit"
                              disabled={loading || deletingId === schedule.id || togglingId === schedule.id}
                            >
                              <Edit className="w-4 h-4" />
                            </Button>
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => handleToggleEnabled(schedule)}
                              title="Toggle Enable/Disable"
                              disabled={togglingId === schedule.id || deletingId === schedule.id}
                            >
                              {togglingId === schedule.id ? (
                                <div className="w-4 h-4 border-2 border-gray-400 border-t-gray-600 rounded-full animate-spin"></div>
                              ) : (
                                schedule.enabled ? 'Disable' : 'Enable'
                              )}
                            </Button>
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => handleDeleteSchedule(schedule.id)}
                              title="Delete"
                              disabled={deletingId === schedule.id || togglingId === schedule.id}
                            >
                              {deletingId === schedule.id ? (
                                <div className="w-4 h-4 border-2 border-red-200 border-t-red-600 rounded-full animate-spin"></div>
                              ) : (
                                <Trash2 className="w-4 h-4 text-red-600" />
                              )}
                            </Button>
                          </>
                        ) : (
                          <span className="text-sm text-muted-foreground">Read only</span>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Add/Edit Schedule Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editingSchedule ? 'Edit Schedule' : 'Add Schedule'}</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Weekly-Backup"
              />
            </div>

            <div>
              <Label htmlFor="intervalDays">Interval (Days)</Label>
              <Select 
                value={formData.intervalDays.toString()} 
                onValueChange={(value) => setFormData({ ...formData, intervalDays: parseInt(value) })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1 (Daily)</SelectItem>
                  <SelectItem value="3">3</SelectItem>
                  <SelectItem value="7">7 (Weekly)</SelectItem>
                  <SelectItem value="14">14</SelectItem>
                  <SelectItem value="30">30 (Monthly)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="runAt">Run At (Time)</Label>
              <Input
                id="runAt"
                type="time"
                value={formData.runAt}
                onChange={(e) => setFormData({ ...formData, runAt: e.target.value })}
              />
              <p className="text-sm text-muted-foreground mt-1">Asia/Jakarta timezone</p>
            </div>

            <div>
              <Label htmlFor="targetType">Target Type</Label>
              <Select 
                value={formData.targetType} 
                onValueChange={(value) => setFormData({ ...formData, targetType: value, targetTags: '' })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All Devices</SelectItem>
                  <SelectItem value="Tag">Specific Tags</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {formData.targetType === 'Tag' && (
              <div>
                <Label htmlFor="targetTags">Select Tags</Label>
                <Select 
                  value={formData.targetTags} 
                  onValueChange={(value) => setFormData({ ...formData, targetTags: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a tag..." />
                  </SelectTrigger>
                  <SelectContent>
                    {availableTags.length === 0 ? (
                      <SelectItem value="__no_tags__" disabled>No tags available</SelectItem>
                    ) : (
                      availableTags.map((tag) => (
                        <SelectItem key={tag} value={tag}>
                          {tag}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
                <p className="text-sm text-muted-foreground mt-1">
                  Backup devices with this tag
                </p>
              </div>
            )}

            <div>
              <Label htmlFor="retention">Retention (keep last N backups)</Label>
              <Input
                id="retention"
                type="number"
                value={formData.retention}
                onChange={(e) => setFormData({ ...formData, retention: parseInt(e.target.value) || 10 })}
                min="1"
              />
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="notifyOnFail"
                checked={formData.notifyOnFail}
                onCheckedChange={(checked) => setFormData({ ...formData, notifyOnFail: checked as boolean })}
              />
              <Label htmlFor="notifyOnFail" className="cursor-pointer">
                Notify on failure
              </Label>
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                id="enabled"
                checked={formData.enabled}
                onCheckedChange={(checked) => setFormData({ ...formData, enabled: checked })}
              />
              <Label htmlFor="enabled" className="cursor-pointer">
                Enabled
              </Label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)} disabled={savingSchedule}>
              Cancel
            </Button>
            <Button onClick={handleSaveSchedule} disabled={savingSchedule}>
              {savingSchedule ? (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  Saving...
                </div>
              ) : (
                'Save'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}