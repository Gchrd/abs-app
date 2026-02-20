"use client";

import { useState, useEffect } from 'react';
import { apiGet, apiPost, apiPut, apiDelete } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Plus, Search, Trash2, Edit, TestTube, CheckCircle, XCircle } from 'lucide-react';
import { toast } from 'sonner';

interface Device {
  id: number | string;
  hostname: string;
  ip: string;
  vendor: string;
  protocol: string;
  port: number | string;
  tags?: string | null;
  last_backup?: string; // Matching backend JSON key (snake_case)
  enabled?: boolean;
}

export function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [savingDevice, setSavingDevice] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [togglingId, setTogglingId] = useState<string | number | null>(null);
  const [userRole] = useState<'admin' | 'viewer' | null>(() => {
    try {
      const u = typeof window !== 'undefined' ? localStorage.getItem('abs_user') : null;
      if (u) return JSON.parse(u)?.role ?? null;
    } catch {
      // ignore
    }
    return null;
  });
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);
  const [formData, setFormData] = useState({
    hostname: '',
    ip: '',
    vendor: 'Cisco',
    protocol: 'SSH',
    port: '22',
    username: '',
    password: '',
    secret: '',
    tags: '',
  });

  const vendors = [
    // Cisco devices
    'Cisco (IOS Router/Switch)',
    'Cisco (ASA Firewall)',
    'Cisco (NXOS Data Center)',
    'Cisco (WLC Controller)',

    // Allied Telesis
    'Allied Telesis (AWPlus)',

    // Aruba devices
    'Aruba (AOS-CX Switch)',
    'Aruba (AOS AP/Controller)',

    // MikroTik devices
    'MikroTik (RouterOS)',
    'MikroTik (SwitchOS)',

    // Huawei devices
    'Huawei (Switch/AP)',
    'Huawei (OLT)',
    'Huawei (SmartAX)',

    // Fortinet devices
    'Fortinet (FortiGate)',

    // Juniper devices
    'Juniper (JunOS)',
  ];

  const filteredDevices = devices.filter(device =>
    device.hostname.toLowerCase().includes(searchQuery.toLowerCase()) ||
    device.ip.includes(searchQuery)
  );

  const handleAddDevice = () => {
    setEditingDevice(null);
    setFormData({
      hostname: '',
      ip: '',
      vendor: 'Cisco (IOS Router/Switch)',
      protocol: 'SSH',
      port: '22',
      username: '',
      password: '',
      secret: '',
      tags: '',
    });
    setIsDialogOpen(true);
  };

  const handleEditDevice = (device: Device) => {
    setEditingDevice(device);
    setFormData({
      hostname: device.hostname,
      ip: device.ip,
      vendor: device.vendor,
      protocol: device.protocol,
      port: String(device.port),
      username: '',
      password: '',
      secret: '',
      tags: '',
    });
    setIsDialogOpen(true);
  };

  const handleSaveDevice = async () => {
    if (!formData.hostname || !formData.ip || !formData.username || !formData.password) {
      toast.error('Please fill in all required fields');
      return;
    }

    setSavingDevice(true);
    try {
      const payload = {
        hostname: formData.hostname,
        ip: formData.ip,
        vendor: formData.vendor,
        protocol: formData.protocol,
        port: Number(formData.port),
        username: formData.username,
        password: formData.password,
        secret: formData.secret || undefined,
        tags: formData.tags || undefined,
      };
      if (editingDevice) {
        await apiPut(`/devices/${editingDevice.id}`, payload);
        toast.success('Device updated successfully');
      } else {
        await apiPost<typeof payload, unknown>(`/devices`, payload);
        toast.success('Device added successfully');
      }
      await fetchDevices();
      setIsDialogOpen(false);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to save device: ' + (msg || 'Unknown error'));
    } finally {
      setSavingDevice(false);
    }
  };

  const handleDeleteDevice = async (id: string) => {
    if (!confirm('Are you sure you want to delete this device?')) {
      return;
    }

    setDeletingId(id);
    try {
      await apiDelete(`/devices/${id}`);
      toast.success('Device deleted successfully');
      await fetchDevices();
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to delete device: ' + (msg || 'Unknown error'));
    } finally {
      setDeletingId(null);
    }
  };

  const handleToggleEnabled = async (device: Device) => {
    setTogglingId(device.id);
    try {
      const newEnabledState = !device.enabled;
      // Update device with only the enabled field changed
      await apiPut(`/devices/${device.id}`, {
        hostname: device.hostname,
        ip: device.ip,
        vendor: device.vendor,
        protocol: device.protocol,
        port: Number(device.port),
        username: '', // backend should ignore empty username/password on update
        password: '',
        tags: device.tags || undefined,
        enabled: newEnabledState,
      });
      // Update local state
      setDevices(prev => prev.map(d =>
        d.id === device.id ? { ...d, enabled: newEnabledState } : d
      ));
      toast.success(`Device ${newEnabledState ? 'enabled' : 'disabled'} successfully`);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to toggle device: ' + (msg || 'Unknown error'));
    } finally {
      setTogglingId(null);
    }
  };

  const handleTestConnection = async (deviceId?: number | string) => {
    setIsTestDialogOpen(true);
    setTestResult(null);
    setTestingConnection(true);
    try {
      if (!deviceId && editingDevice) deviceId = editingDevice.id;
      const res = await apiPost<unknown, { success: boolean; message: string }>(`/devices/${deviceId}/test`, {} as unknown);
      setTestResult(res);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      setTestResult({ success: false, message: msg || 'Connection test failed' });
    } finally {
      setTestingConnection(false);
    }
  };

  const fetchDevices = async () => {
    setLoading(true);
    try {
      const rows = await apiGet<Device[]>('/devices');
      setDevices(rows);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to load devices: ' + (msg || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-gray-900">Devices</h2>
          <p className="text-gray-500">Manage network devices for backup</p>
        </div>
        {userRole === 'admin' && (
          <Button onClick={handleAddDevice} className="gap-2" disabled={loading}>
            <Plus className="w-4 h-4" />
            Add Device
          </Button>
        )}
      </div>

      {/* Search Box */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
        <Input
          placeholder="Search devices..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Info Banner */}
      {devices.some(d => d.enabled === false) && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <p className="text-yellow-800 text-sm">
            ⚠️ Disabled devices will be excluded from manual and scheduled backup jobs.
          </p>
        </div>
      )}

      {/* Devices Groups */}
      <div className="space-y-8">
        {loading && devices.length === 0 ? (
          <div className="flex items-center justify-center py-12 border rounded-lg bg-white">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
              <p className="text-gray-500">Loading devices...</p>
            </div>
          </div>
        ) : (
          <>
            {['Core & Backbone', 'Access Switches', 'Wireless', 'Routing & Specialty'].map((groupName) => {
              const groupDevices = filteredDevices.filter(d => {
                const hostname = d.hostname.toLowerCase();
                const vendor = d.vendor.toLowerCase();
                const tags = (d.tags || '').toLowerCase();

                let assignedGroup = 'Access Switches'; // Default Fallback

                // 1. Priority: Check Tags explicitly
                if (tags.includes('core')) assignedGroup = 'Core & Backbone';
                else if (tags.includes('wifi') || tags.includes('ap') || tags.includes('wireless')) assignedGroup = 'Wireless';
                else if (tags.includes('router') || tags.includes('routing') || tags.includes('mikrotik') || tags.includes('iot')) assignedGroup = 'Routing & Specialty';
                else if (tags.includes('access')) assignedGroup = 'Access Switches';

                // 2. Fallback: Heuristic (Guess based on Vendor/Hostname)
                // Only if no specific tag was found (i.e. if it fell through to default above, we check heuristics to potentially move it)
                else {
                  if (vendor.includes('fortinet') || hostname.includes('core')) assignedGroup = 'Core & Backbone';
                  else if (vendor.includes('aruba') || hostname.includes('ap')) assignedGroup = 'Wireless';
                  else if (vendor.includes('mikrotik') || hostname.includes('door')) assignedGroup = 'Routing & Specialty';
                  // else remains 'Access Switches'
                }

                return assignedGroup === groupName;
              });

              if (groupDevices.length === 0) return null;

              return (
                <div key={groupName} className="border rounded-lg bg-white overflow-hidden">
                  <div className="bg-gray-50 px-4 py-3 border-b flex items-center justify-between">
                    <h3 className="font-semibold text-gray-700">{groupName}</h3>
                    <Badge variant="secondary" className="text-xs">
                      {groupDevices.length} Devices
                    </Badge>
                  </div>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Hostname</TableHead>
                        <TableHead>IP</TableHead>
                        <TableHead>Vendor</TableHead>
                        <TableHead>Protocol</TableHead>
                        <TableHead>Port</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Last Backup</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {groupDevices.map((device) => {
                        const isEnabled = device.enabled !== false;
                        return (
                          <TableRow key={device.id}>
                            <TableCell className="font-medium">{device.hostname}</TableCell>
                            <TableCell>{device.ip}</TableCell>
                            <TableCell>{device.vendor}</TableCell>
                            <TableCell>{device.protocol}</TableCell>
                            <TableCell>{device.port}</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                {userRole === 'admin' ? (
                                  <Switch
                                    checked={isEnabled}
                                    onCheckedChange={() => handleToggleEnabled(device)}
                                    className="data-[state=checked]:bg-green-600"
                                    disabled={togglingId === device.id}
                                  />
                                ) : null}
                                <Badge className={isEnabled ? 'bg-green-100 text-green-700 hover:bg-green-100' : 'bg-gray-100 text-gray-700 hover:bg-gray-100'}>
                                  {isEnabled ? 'Enabled' : 'Disabled'}
                                </Badge>
                              </div>
                            </TableCell>
                            <TableCell>
                              {device.last_backup
                                ? new Date(device.last_backup).toLocaleString('id-ID', {
                                  day: 'numeric', month: 'short', year: 'numeric',
                                  hour: '2-digit', minute: '2-digit'
                                })
                                : '-'
                              }
                            </TableCell>
                            <TableCell>
                              <div className="flex gap-2">
                                {userRole === 'admin' ? (
                                  <>
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => {
                                        handleEditDevice(device);
                                        setTimeout(() => handleTestConnection(device.id), 100);
                                      }}
                                      title="Test Connection"
                                      disabled={testingConnection || loading}
                                    >
                                      <TestTube className="w-4 h-4" />
                                    </Button>
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => handleEditDevice(device)}
                                      title="Edit"
                                      disabled={loading}
                                    >
                                      <Edit className="w-4 h-4" />
                                    </Button>
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => handleDeleteDevice(String(device.id))}
                                      title="Delete"
                                      disabled={deletingId === String(device.id)}
                                    >
                                      {deletingId === String(device.id) ? (
                                        <div className="w-4 h-4 border-2 border-red-200 border-t-red-600 rounded-full animate-spin"></div>
                                      ) : (
                                        <Trash2 className="w-4 h-4 text-red-600" />
                                      )}
                                    </Button>
                                  </>
                                ) : (
                                  <Button variant="outline" size="sm" onClick={() => handleTestConnection(device.id)} title="Test Connection" disabled={testingConnection}>
                                    <TestTube className="w-4 h-4" />
                                  </Button>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* Add/Edit Device Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingDevice ? 'Edit Device' : 'Add Device'}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="vendor">Vendor</Label>
              <Select
                value={formData.vendor}
                onValueChange={(value) => setFormData({ ...formData, vendor: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {vendors.map((vendor) => (
                    <SelectItem key={vendor} value={vendor}>{vendor}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="hostname">Hostname</Label>
              <Input
                id="hostname"
                value={formData.hostname}
                onChange={(e) => setFormData({ ...formData, hostname: e.target.value })}
                placeholder="SW-01"
              />
            </div>

            <div>
              <Label htmlFor="ip">IP Address</Label>
              <Input
                id="ip"
                value={formData.ip}
                onChange={(e) => setFormData({ ...formData, ip: e.target.value })}
                placeholder="10.2.8.1"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="protocol">Protocol</Label>
                <Select
                  value={formData.protocol}
                  onValueChange={(value) => {
                    setFormData({
                      ...formData,
                      protocol: value,
                      port: value === 'SSH' ? '22' : '23'
                    });
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="SSH">SSH</SelectItem>
                    <SelectItem value="Telnet">Telnet</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="port">Port</Label>
                <Input
                  id="port"
                  value={formData.port}
                  onChange={(e) => setFormData({ ...formData, port: e.target.value })}
                />
              </div>
            </div>

            <div>
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                placeholder="admin"
              />
            </div>

            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder={editingDevice ? 'Leave empty to keep current' : ''}
              />
            </div>

            <div>
              <Label htmlFor="secret">Secret (enable) - Optional</Label>
              <Input
                id="secret"
                type="password"
                value={formData.secret}
                onChange={(e) => setFormData({ ...formData, secret: e.target.value })}
                placeholder="Optional enable secret"
              />
            </div>

            <div>
              <Label htmlFor="tags">Tags - Optional</Label>
              <Input
                id="tags"
                value={formData.tags}
                onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                placeholder="production, core, edge"
              />
            </div>

            <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-600">
              💡 Device credentials are stored encrypted and never shown again.
              {!editingDevice && (
                <div className="mt-2 text-blue-600">
                  ℹ️ Tip: Save the device first, then use Edit → Test Connection to verify connectivity.
                </div>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)} disabled={savingDevice || testingConnection}>
              Cancel
            </Button>
            {/* Only show Test Connection button when editing existing device */}
            {editingDevice && (
              <Button onClick={() => handleTestConnection()} disabled={savingDevice || testingConnection}>
                {testingConnection ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Testing...
                  </div>
                ) : (
                  'Test Connection'
                )}
              </Button>
            )}
            <Button onClick={handleSaveDevice} disabled={savingDevice || testingConnection}>
              {savingDevice ? (
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

      {/* Test Connection Dialog */}
      <Dialog open={isTestDialogOpen} onOpenChange={setIsTestDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Testing Connection</DialogTitle>
          </DialogHeader>

          <div className="py-6">
            {testResult === null ? (
              <div className="flex flex-col items-center gap-4">
                <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
                <p className="text-gray-600">Connecting to device...</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-4">
                {testResult.success ? (
                  <CheckCircle className="w-16 h-16 text-green-600" />
                ) : (
                  <XCircle className="w-16 h-16 text-red-600" />
                )}
                <p className={testResult.success ? 'text-green-600' : 'text-red-600'}>
                  {testResult.message}
                </p>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button onClick={() => setIsTestDialogOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}