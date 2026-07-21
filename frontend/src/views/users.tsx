"use client";

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Plus, Trash2, Key } from 'lucide-react';
import { toast } from 'sonner';
import { apiGet, apiPost, apiPut, apiDelete } from '@/lib/api';

interface User {
  id: number;
  username: string;
  role: 'admin' | 'viewer';
  created_at: string; // from backend
}

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingUser, setSavingUser] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [resettingPassword, setResettingPassword] = useState(false);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isResetDialogOpen, setIsResetDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [addFormData, setAddFormData] = useState({
    username: '',
    password: '',
    role: 'viewer' as 'admin' | 'viewer',
  });
  const [resetFormData, setResetFormData] = useState({
    newPassword: '',
    confirmPassword: '',
  });

  const handleAddUser = async () => {
    if (!addFormData.username || !addFormData.password) {
      toast.error('Please fill in all required fields');
      return;
    }

    if (addFormData.password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }

    setSavingUser(true);
    try {
      await apiPost('/users', {
        username: addFormData.username,
        password: addFormData.password,
        role: addFormData.role,
      });
      setIsAddDialogOpen(false);
      setAddFormData({ username: '', password: '', role: 'viewer' });
      toast.success('User added successfully');
      await fetchUsers();
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to add user: ' + (msg || 'Unknown error'));
    } finally {
      setSavingUser(false);
    }
  };

  const handleDeleteUser = async (user: User) => {
    const adminCount = users.filter(u => u.role === 'admin').length;

    if (user.role === 'admin' && adminCount <= 1) {
      toast.error('Cannot delete the last admin user');
      return;
    }

    if (!confirm(`Are you sure you want to delete user "${user.username}"?`)) {
      return;
    }

    setDeletingId(user.id);
    try {
      await apiDelete(`/users/${user.id}`);
      toast.success('User deleted successfully');
      await fetchUsers();
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to delete user: ' + (msg || 'Unknown error'));
    } finally {
      setDeletingId(null);
    }
  };

  const handleResetPassword = async () => {
    if (!resetFormData.newPassword || !resetFormData.confirmPassword) {
      toast.error('Please fill in all fields');
      return;
    }

    if (resetFormData.newPassword.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }

    if (resetFormData.newPassword !== resetFormData.confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    if (!selectedUser) {
      toast.error('No user selected');
      return;
    }

    setResettingPassword(true);
    try {
      await apiPut(`/users/${selectedUser.id}`, { password: resetFormData.newPassword });
      setIsResetDialogOpen(false);
      setResetFormData({ newPassword: '', confirmPassword: '' });
      toast.success('Password reset successfully');
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to reset password: ' + (msg || 'Unknown error'));
    } finally {
      setResettingPassword(false);
    }
  };

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await apiGet<User[]>('/users');
      setUsers(data);
    } catch (err: unknown) {
      const msg = (err && typeof err === 'object' && 'message' in err) ? (err as { message?: string }).message : String(err);
      toast.error('Failed to load users: ' + (msg || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const getCurrentUserRole = () => {
    try {
      if (typeof window === 'undefined') return 'viewer';
      const u = localStorage.getItem('abs_user');
      if (!u) return 'viewer';
      return JSON.parse(u).role as 'admin' | 'viewer';
    } catch (e) {
      return 'viewer';
    }
  };

  const isAdmin = getCurrentUserRole() === 'admin';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-foreground">Users</h2>
          <p className="text-muted-foreground">Manage web application accounts</p>
        </div>
        {isAdmin && (
          <Button onClick={() => setIsAddDialogOpen(true)} className="gap-2" disabled={loading}>
          <Plus className="w-4 h-4" />
          Add User
          </Button>
        )}
      </div>

      {/* Users Table */}
      <div className="border rounded-lg bg-card">
        {loading && users.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
              <p className="text-muted-foreground">Loading users...</p>
            </div>
          </div>
        ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Username</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Created At</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((user) => (
              <TableRow key={user.id}>
                <TableCell>{user.username}</TableCell>
                <TableCell>
                  <span className={`px-2 py-1 rounded text-sm ${
                    user.role === 'admin' 
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300' 
                      : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                  }`}>
                    {user.role}
                  </span>
                </TableCell>
                <TableCell>{new Date(user.created_at).toLocaleString()}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    {isAdmin ? (
                      <>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => {
                            setSelectedUser(user);
                            setIsResetDialogOpen(true);
                          }}
                          title="Reset Password"
                          className="gap-2"
                          disabled={loading || deletingId === user.id}
                        >
                          <Key className="w-4 h-4" />
                          Reset PW
                        </Button>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => handleDeleteUser(user)}
                          title="Delete"
                          className="gap-2"
                          disabled={deletingId === user.id}
                        >
                          {deletingId === user.id ? (
                            <div className="w-4 h-4 border-2 border-red-200 border-t-red-600 rounded-full animate-spin"></div>
                          ) : (
                            <Trash2 className="w-4 h-4 text-red-600" />
                          )}
                          {deletingId === user.id ? 'Deleting...' : 'Delete'}
                        </Button>
                      </>
                    ) : (
                      <span className="text-sm text-muted-foreground">Read only</span>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        )}
      </div>

      {/* Add User Dialog */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add User</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={addFormData.username}
                onChange={(e) => setAddFormData({ ...addFormData, username: e.target.value })}
                placeholder="Enter username"
              />
            </div>

            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={addFormData.password}
                onChange={(e) => setAddFormData({ ...addFormData, password: e.target.value })}
                placeholder="Enter password"
              />
            </div>

            <div>
              <Label htmlFor="role">Role</Label>
              <Select 
                value={addFormData.role} 
                onValueChange={(value) => setAddFormData({ ...addFormData, role: value as 'admin' | 'viewer' })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">admin</SelectItem>
                  <SelectItem value="viewer">viewer</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddDialogOpen(false)} disabled={savingUser}>
              Cancel
            </Button>
            <Button onClick={handleAddUser} disabled={savingUser}>
              {savingUser ? (
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

      {/* Reset Password Dialog */}
      <Dialog open={isResetDialogOpen} onOpenChange={setIsResetDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Reset Password - {selectedUser?.username}</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="newPassword">New Password</Label>
              <Input
                id="newPassword"
                type="password"
                value={resetFormData.newPassword}
                onChange={(e) => setResetFormData({ ...resetFormData, newPassword: e.target.value })}
                placeholder="Enter new password"
              />
            </div>

            <div>
              <Label htmlFor="confirmPassword">Confirm Password</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={resetFormData.confirmPassword}
                onChange={(e) => setResetFormData({ ...resetFormData, confirmPassword: e.target.value })}
                placeholder="Confirm new password"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsResetDialogOpen(false)} disabled={resettingPassword}>
              Cancel
            </Button>
            <Button onClick={handleResetPassword} disabled={resettingPassword}>
              {resettingPassword ? (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  Resetting...
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