import { useState, useEffect, type FC } from 'react';
import { Card } from '../components/ui/Card';
import { api } from '../lib/api';

interface User {
  id: string;
  email: string;
  role: 'admin' | 'user' | 'viewer';
  active: boolean;
  created_at: string;
}

export const AdminUsers: FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchUsers() {
      try {
        const res = await api.get('/api/admin/users');
        setUsers(res.data?.users || []);
      } catch (err) {
        console.warn('[AdminUsers] failed to load users:', err)
      } finally {
        setLoading(false);
      }
    }
    fetchUsers();
  }, []);

  const toggleActive = async (userId: string, active: boolean) => {
    try {
      await api.patch(`/api/admin/users/${userId}`, { active: !active });
      setUsers(prev =>
        prev.map(u => u.id === userId ? { ...u, active: !active } : u)
      );
    } catch (err) {
      console.warn('[AdminUsers] failed to toggle user:', err)
    }
  };

  return (
    <div className="mx-auto max-w-6xl p-6 space-y-6">
      <h1 className="text-3xl font-bold text-drs-text">User Management</h1>

      <Card>
        {loading ? (
          <p className="text-sm text-drs-faint">Loading users...</p>
        ) : users.length === 0 ? (
          <p className="text-sm text-drs-muted">No users found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-drs-border text-left text-drs-muted">
                  <th className="pb-2">Email</th>
                  <th className="pb-2">Role</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Created</th>
                  <th className="pb-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-b border-drs-border">
                    <td className="py-2 text-drs-text">{user.email}</td>
                    <td className="py-2">
                      <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
                        user.role === 'admin' ? 'bg-drs-accent/20 text-drs-accent' :
                        'bg-drs-s3 text-drs-muted'
                      }`}>
                        {user.role}
                      </span>
                    </td>
                    <td className="py-2">
                      <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
                        user.active ? 'bg-drs-green/20 text-drs-green' : 'bg-drs-red/20 text-drs-red'
                      }`}>
                        {user.active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="py-2 text-drs-faint">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-2">
                      <button
                        onClick={() => toggleActive(user.id, user.active)}
                        className="text-sm text-drs-accent hover:brightness-110"
                      >
                        {user.active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};
