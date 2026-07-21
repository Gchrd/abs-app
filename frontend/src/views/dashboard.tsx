"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { HardDrive, CheckCircle, XCircle, RefreshCw, AlertCircle } from "lucide-react";
import { useState, useEffect } from "react";
import { apiGet } from "@/lib/api";
import { KpiStrip } from "@/components/dashboard/kpi-strip";
import { QuickSearchDownload } from "@/components/dashboard/quick-search-download";
import { BackupChangesWidget } from "@/components/dashboard/backup-changes-widget";

interface Job {
  id: number;
  triggered_by: string;
  devices: number;
  status: string;
  started_at: string;
  finished_at: string;
}

interface Device {
  id: number;
  hostname: string;
  enabled: boolean;
}

interface ActiveBackup {
  device_id: number;
  status_changed: boolean;
}

export function DashboardPage() {
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

  const [stats, setStats] = useState({
    totalDevices: 0,
    successfulBackups: 0,
    failedBackups: 0,
    changedBackups: 0,
  });
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        // Fetch devices
        const devices = await apiGet<Device[]>('/devices');
        const totalDevices = devices.length;

        // Fetch devices with changed (unacknowledged) config
        const activeBackups = await apiGet<ActiveBackup[]>('/backups/active');
        const changedBackups = activeBackups.filter(ab => ab.status_changed).length;

        // Fetch recent jobs
        const jobs = await apiGet<Job[]>('/jobs');
        setRecentJobs(jobs.slice(0, 5)); // Top 5 recent jobs

        // Calculate backup stats from recent jobs (last 7 days)
        const sevenDaysAgo = new Date();
        sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

        const recentJobsLast7Days = jobs.filter(job => {
          const jobDate = new Date(job.started_at);
          return jobDate >= sevenDaysAgo;
        });

        const successfulBackups = recentJobsLast7Days.filter(j => j.status === 'success').length;
        const failedBackups = recentJobsLast7Days.filter(j => j.status === 'failed').length;

        setStats({
          totalDevices,
          successfulBackups,
          failedBackups,
          changedBackups,
        });
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      }
    };

    fetchDashboardData();
  }, []);

  const kpiItems = [
    { label: 'Total Devices', value: stats.totalDevices.toString(), icon: HardDrive, colorClass: 'text-blue-600 dark:text-blue-400' },
    { label: 'Successful Backups (7 days)', value: stats.successfulBackups.toString(), icon: CheckCircle, colorClass: 'text-green-600 dark:text-green-400' },
    { label: 'Failed Backups (7 days)', value: stats.failedBackups.toString(), icon: XCircle, colorClass: 'text-red-600 dark:text-red-400' },
    { label: 'Backup Changes', value: stats.changedBackups.toString(), icon: RefreshCw, colorClass: 'text-orange-600 dark:text-orange-400' },
  ];

  const getStatusBadge = (status: string) => {
    const variants = {
      success: 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300',
      failed: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
      running: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300',
    };
    return <Badge className={variants[status as keyof typeof variants] || ''}>{status}</Badge>;
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-foreground">Dashboard</h2>
        <p className="text-muted-foreground">Overview of your backup system</p>
      </div>

      {/* Viewer Info Banner */}
      {userRole === 'viewer' && (
        <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-900 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5" />
          <div>
            <p className="text-blue-800 dark:text-blue-200 font-medium">Viewing in read-only mode</p>
            <p className="text-blue-700 dark:text-blue-300 text-sm mt-1">
              You are logged in as a viewer. Some features like adding/editing devices, users, and schedules are restricted to admin users.
            </p>
          </div>
        </div>
      )}

      {/* KPI Strip */}
      <KpiStrip items={kpiItems} />

      {/* Quick Search & Backup Changes Widgets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <QuickSearchDownload />
        <BackupChangesWidget />
      </div>

      {/* Recent Jobs Table */}
      <Card>
        <CardContent className="p-6">
          <h3 className="text-foreground mb-4">Recent Jobs</h3>
          <div className="border rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job ID</TableHead>
                  <TableHead>Devices</TableHead>
                  <TableHead>Trigger</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Started At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentJobs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      No jobs yet. Run your first backup from the Jobs page.
                    </TableCell>
                  </TableRow>
                ) : (
                  recentJobs.map((job) => {
                    const startedDate = new Date(job.started_at);
                    const finishedDate = job.finished_at ? new Date(job.finished_at) : null;
                    const duration = finishedDate 
                      ? Math.floor((finishedDate.getTime() - startedDate.getTime()) / 1000 / 60) + 'm'
                      : '-';
                    const startedAt = startedDate.toLocaleString('en-US', { 
                      month: '2-digit', 
                      day: '2-digit', 
                      hour: '2-digit', 
                      minute: '2-digit',
                      hour12: false 
                    });

                    return (
                      <TableRow key={job.id}>
                        <TableCell>#{job.id}</TableCell>
                        <TableCell>{job.devices || 0}</TableCell>
                        <TableCell>{job.triggered_by}</TableCell>
                        <TableCell>{getStatusBadge(job.status)}</TableCell>
                        <TableCell>{duration}</TableCell>
                        <TableCell>{startedAt}</TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}