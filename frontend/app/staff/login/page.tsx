'use client';
import { useState } from 'react';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { Button, Input, Card } from '@/components/ui';

export default function StaffLogin() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('demo1234');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await api<any>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password })
      });
      if (res && res.access_token) {
        localStorage.setItem('access_token', res.access_token);
        // Force a reload to clear any query cache and correctly redirect
        window.location.href = '/staff/works';
      } else {
        setError('Login failed');
      }
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-gray-100">
      <Card className="w-full max-w-md p-6 bg-white shadow-lg rounded-lg">
        <h1 className="text-2xl font-bold mb-6 text-center text-gray-800">Staff Console Login</h1>
        {error && <div className="bg-red-50 text-red-600 p-3 rounded mb-4 text-sm">{error}</div>}
        <form onSubmit={handleLogin} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <Input 
              type="email" 
              value={email} 
              onChange={e => setEmail(e.target.value)} 
              placeholder="je.ward1@demo.city" 
              required 
              className="w-full border p-2 rounded"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <Input 
              type="password" 
              value={password} 
              onChange={e => setPassword(e.target.value)} 
              required 
              className="w-full border p-2 rounded"
            />
          </div>
          <Button type="submit" disabled={loading} className="w-full mt-2 bg-blue-600 text-white p-2 rounded hover:bg-blue-700">
            {loading ? 'Logging in...' : 'Login'}
          </Button>
        </form>
        <div className="mt-4 text-xs text-gray-500 text-center">
          Test accounts: je.ward1@demo.city, ee.roads@demo.city, utility.water@demo.city, auditor@demo.city (pwd: demo1234)
        </div>
      </Card>
      <style dangerouslySetInnerHTML={{__html: `
        .site-header, .site-footer { display: none !important; }
        #main-content { padding: 0 !important; max-width: none !important; margin: 0 !important; }
      `}} />
    </div>
  );
}
