"use client";

import { useState, useEffect } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { apiGet } from '@/lib/api';
import { toast } from 'sonner';

interface AuditLog {
  id: number;
  timestamp: string;
  user: string;
  action: string;
  target: string;
  result: string;
}

export function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [userFilter, setUserFilter] = useState('All');
  const [currentPage, setCurrentPage] = useState(1);
  const logsPerPage = 20;

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await apiGet<AuditLog[]>('/audit-logs');
      setLogs(data);
    } catch (err) {
      toast.error(`Failed to fetch audit logs: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const users = ['All', ...Array.from(new Set(logs.map(l => l.user)))];

  const filteredLogs = logs.filter(log => {
    const matchesUser = userFilter === 'All' || log.user === userFilter;
    return matchesUser;
  });

  // Pagination
  const totalPages = Math.ceil(filteredLogs.length / logsPerPage);
  const startIndex = (currentPage - 1) * logsPerPage;
  const endIndex = startIndex + logsPerPage;
  const paginatedLogs = filteredLogs.slice(startIndex, endIndex);

  const getResultBadge = (result: string) => {
    const isSuccess = result === 'success' || result.startsWith('success');
    const variants = {
      success: 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300',
      failed: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
    };
    return (
      <Badge className={isSuccess ? variants.success : variants.failed}>
        {result}
      </Badge>
    );
  };

  const getActionColor = (action: string) => {
    if (action.startsWith('auth_')) return 'text-blue-600';
    if (action.startsWith('job_')) return 'text-purple-600';
    if (action.startsWith('device_')) return 'text-green-600';
    if (action.startsWith('user_')) return 'text-orange-600';
    if (action.startsWith('schedule_')) return 'text-indigo-600';
    if (action.startsWith('backup_')) return 'text-teal-600';
    if (action.startsWith('retention_')) return 'text-muted-foreground';
    return 'text-muted-foreground';
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-foreground">Audit Logs</h2>
        <p className="text-muted-foreground">Track all important system actions and events</p>
      </div>

      {/* Filters */}
      <div className="flex gap-4 flex-wrap items-center">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">User:</span>
          <Select value={userFilter} onValueChange={setUserFilter}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {users.map(user => (
                <SelectItem key={user} value={user}>{user}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <button
          onClick={fetchLogs}
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
          disabled={loading}
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {/* Info Box */}
      <div className="bg-muted border border-border rounded-lg p-4">
        <p className="text-sm text-foreground mb-2">📝 Audit logs track the following events:</p>
        <div className="grid grid-cols-2 gap-2 text-sm text-muted-foreground">
          <div>
            <span className="text-blue-600">• auth_*</span> - Login attempts
          </div>
          <div>
            <span className="text-purple-600">• job_*</span> - Job operations
          </div>
          <div>
            <span className="text-green-600">• device_*</span> - Device CRUD & tests
          </div>
          <div>
            <span className="text-orange-600">• user_*</span> - User management
          </div>
          <div>
            <span className="text-indigo-600">• schedule_*</span> - Schedule operations
          </div>
          <div>
            <span className="text-teal-600">• backup_*</span> - Backup downloads
          </div>
        </div>
      </div>

      {/* Audit Logs Table */}
      <div className="border rounded-lg bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Timestamp</TableHead>
              <TableHead>User</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Target</TableHead>
              <TableHead>Result</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedLogs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                  {loading ? 'Loading audit logs...' : 'No audit logs found'}
                </TableCell>
              </TableRow>
            ) : (
              paginatedLogs.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="text-muted-foreground">{formatTimestamp(log.timestamp)}</TableCell>
                  <TableCell>
                    <span className={`px-2 py-1 rounded text-sm ${
                      log.user === 'admin'
                        ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
                        : log.user === 'system'
                        ? 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                        : 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300'
                    }`}>
                      {log.user}
                    </span>
                  </TableCell>
                  <TableCell>
                    <code className={`text-sm ${getActionColor(log.action)}`}>
                      {log.action}
                    </code>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{log.target}</TableCell>
                  <TableCell>{getResultBadge(log.result)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Showing {startIndex + 1}-{Math.min(endIndex, filteredLogs.length)} of {filteredLogs.length} entries
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="px-3 py-1 text-sm border rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-muted"
          >
            Previous
          </button>
          <span className="px-3 py-1 text-sm">
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
    </div>
  );
}