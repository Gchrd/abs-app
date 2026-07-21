"use client";

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Play, Eye, X } from 'lucide-react';
import { toast } from 'sonner';
import { apiGet, apiPost } from '@/lib/api';

interface Job {
  id: number;
  triggeredBy: string;
  devices: number;
  status: 'running' | 'success' | 'failed' | 'queued';
  startedAt: string | null;
  finishedAt: string | null;
  log?: string | null;
}

  type ApiJob = {
    id: number;
    triggered_by?: string;
    triggeredBy?: string;
    devices?: number;
    status: string;
    started_at?: string;
    startedAt?: string;
    finished_at?: string;
    finishedAt?: string;
    log?: string;
  };

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [runningManual, setRunningManual] = useState(false);
  const [cancellingId, setCancellingId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState('All');
  const [currentPage, setCurrentPage] = useState(1);
  const jobsPerPage = 20;
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [jobLog, setJobLog] = useState<string[]>([]);
  const [loadingLog, setLoadingLog] = useState(false);

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

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const data = await apiGet<ApiJob[]>('/jobs');
      const mapped = data.map((j) => ({
        id: j.id,
        triggeredBy: j.triggered_by ?? j.triggeredBy ?? '',
        devices: j.devices ?? 0,
        status: j.status as Job['status'],
        startedAt: j.started_at ?? j.startedAt ?? null,
        finishedAt: j.finished_at ?? j.finishedAt ?? null,
        log: j.log ?? null,
      }));
      setJobs(mapped);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to load jobs: ' + (msg || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!mounted) return;
      await fetchJobs();
    })();
    const interval = setInterval(() => {
      if (mounted) fetchJobs();
    }, 5000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  const filteredJobs = statusFilter === 'All'
    ? jobs
    : jobs.filter(job => job.status === statusFilter.toLowerCase());

  const totalPages = Math.ceil(filteredJobs.length / jobsPerPage);
  const startIndex = (currentPage - 1) * jobsPerPage;
  const endIndex = startIndex + jobsPerPage;
  const paginatedJobs = filteredJobs.slice(startIndex, endIndex);

  const handleStatusFilterChange = (value: string) => {
    setStatusFilter(value);
    setCurrentPage(1);
  };

  const getStatusBadge = (status: string) => {
    const variants = {
      success: 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300',
      failed: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
      running: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300',
      queued: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
    };
    const icons = {
      success: '✅',
      failed: '❌',
      running: '🟡',
      queued: '⏳',
    };
    return (
      <Badge className={variants[status as keyof typeof variants] || ''}>
        {icons[status as keyof typeof icons]} {status}
      </Badge>
    );
  };

  const handleViewJob = async (job: Job) => {
    setSelectedJob(job);
    setIsDetailOpen(true);
    setLoadingLog(true);
    setJobLog([]);
    
    try {
      const jobDetail = await apiGet<{
        id: number;
        triggered_by: string;
        status: string;
        started_at: string | null;
        finished_at: string | null;
        devices_count: number;
        log: string;
      }>(`/jobs/${job.id}`);
      
      const logLines = jobDetail.log ? jobDetail.log.split('\n').filter(line => line.trim()) : [];
      setJobLog(logLines);
      
      // Update selected job with fresh data
      setSelectedJob({
        ...job,
        triggeredBy: jobDetail.triggered_by,
        devices: jobDetail.devices_count,
        status: jobDetail.status as Job['status'],
        startedAt: jobDetail.started_at,
        finishedAt: jobDetail.finished_at,
        log: jobDetail.log,
      });
    } catch (err) {
      toast.error(`Failed to fetch job details: ${err}`);
    } finally {
      setLoadingLog(false);
    }
  };

  const handleCancelJob = async (jobId: number) => {
    if (!confirm('Are you sure you want to cancel this job?')) {
      return;
    }

    setCancellingId(jobId);
    try {
      await apiPost(`/jobs/${jobId}/cancel`, {});
      toast.success('Job cancelled successfully');
      await fetchJobs();
      setIsDetailOpen(false);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to cancel job: ' + (msg || 'Unknown error'));
    } finally {
      setCancellingId(null);
    }
  };

  const handleRunManual = async () => {
    setRunningManual(true);
    try {
      await apiPost('/jobs/run/manual', {});
      toast.success('Manual backup job queued successfully');
      await fetchJobs();
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to start backup job: ' + (msg || 'Unknown error'));
    } finally {
      setRunningManual(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-foreground">Jobs</h2>
          <p className="text-muted-foreground">Backup job history and status</p>
        </div>
        {userRole === 'admin' && (
          <Button onClick={handleRunManual} className="gap-2" disabled={runningManual || loading}>
            {runningManual ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                Starting...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Run Manual Backup
              </>
            )}
          </Button>
        )}
      </div>

      {/* Status Filter */}
      <div className="flex items-center gap-4">
        <span className="text-sm text-muted-foreground">Filter by status:</span>
        <Select value={statusFilter} onValueChange={handleStatusFilterChange}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All">All</SelectItem>
            <SelectItem value="Running">Running</SelectItem>
            <SelectItem value="Success">Success</SelectItem>
            <SelectItem value="Failed">Failed</SelectItem>
            <SelectItem value="Queued">Queued</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Queue Banner */}
      {jobs.some(job => job.status === 'queued') && (
        <div className="bg-blue-50 border border-blue-200 dark:bg-blue-950 dark:border-blue-900 rounded-lg p-4">
          <p className="text-blue-800 dark:text-blue-300">
            ⏳ 1 job is currently running. Your job is queued and will start automatically.
          </p>
        </div>
      )}

      {/* Jobs Table */}
      <div className="border rounded-lg bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Job ID</TableHead>
              <TableHead>Triggered By</TableHead>
              <TableHead>Devices</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Finished</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedJobs.map((job) => (
              <TableRow key={job.id}>
                <TableCell>{`#${job.id}`}</TableCell>
                <TableCell>{job.triggeredBy}</TableCell>
                <TableCell>{job.devices}</TableCell>
                <TableCell>{getStatusBadge(job.status)}</TableCell>
                <TableCell>{job.startedAt ? new Date(job.startedAt).toLocaleString() : '-'}</TableCell>
                <TableCell>{job.finishedAt ? new Date(job.finishedAt).toLocaleString() : '-'}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => handleViewJob(job)}
                      title="View Details"
                    >
                      <Eye className="w-4 h-4" />
                    </Button>
                    {job.status === 'running' && userRole === 'admin' && (
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleCancelJob(job.id)}
                        title="Cancel Job"
                        disabled={cancellingId === job.id}
                      >
                        {cancellingId === job.id ? (
                          <div className="w-4 h-4 border-2 border-red-200 border-t-red-600 rounded-full animate-spin"></div>
                        ) : (
                          <X className="w-4 h-4 text-red-600" />
                        )}
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {filteredJobs.length > 0 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {startIndex + 1}-{Math.min(endIndex, filteredJobs.length)} of {filteredJobs.length} jobs
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1 text-sm border rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-muted"
            >
              Previous
            </button>
            <span className="px-3 py-1 text-sm text-foreground">
              Page {currentPage} of {totalPages || 1}
            </span>
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages || totalPages === 0}
              className="px-3 py-1 text-sm border rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-muted"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Job Detail Modal */}
      <Dialog open={isDetailOpen} onOpenChange={setIsDetailOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Job {selectedJob?.id} - {selectedJob?.status}</DialogTitle>
          </DialogHeader>
          
          {selectedJob && (
            <div className="space-y-4 py-4">
              <div>
                <h4 className="text-foreground mb-2">Details</h4>
                <div className="space-y-1 text-sm">
                  <p><span className="text-muted-foreground">Triggered by:</span> {selectedJob.triggeredBy}</p>
                  <p><span className="text-muted-foreground">Devices:</span> {selectedJob.devices}</p>
                  <p><span className="text-muted-foreground">Started:</span> {selectedJob.startedAt ? new Date(selectedJob.startedAt).toLocaleString() : '-'}</p>
                  <p><span className="text-muted-foreground">Finished:</span> {selectedJob.finishedAt ? new Date(selectedJob.finishedAt).toLocaleString() : '-'}</p>
                </div>
              </div>

              <div>
                <h4 className="text-foreground mb-2">Logs</h4>
                <div className="bg-gray-900 text-green-400 p-4 rounded-lg h-64 overflow-auto font-mono text-sm">
                  {loadingLog ? (
                    <div className="text-yellow-400 animate-pulse">Loading logs...</div>
                  ) : jobLog.length > 0 ? (
                    jobLog.map((log, index) => (
                      <div key={index}>{log}</div>
                    ))
                  ) : (
                    <div className="text-gray-500">No logs available yet</div>
                  )}
                  {selectedJob.status === 'running' && jobLog.length > 0 && (
                    <div className="animate-pulse mt-2">Processing...</div>
                  )}
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            {selectedJob?.status === 'running' && userRole === 'admin' && (
              <Button 
                variant="destructive" 
                onClick={() => selectedJob && handleCancelJob(selectedJob.id)}
                disabled={cancellingId === selectedJob.id}
              >
                {cancellingId === selectedJob.id ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Cancelling...
                  </div>
                ) : (
                  'Cancel Job'
                )}
              </Button>
            )}
            <Button variant="outline" onClick={() => setIsDetailOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}