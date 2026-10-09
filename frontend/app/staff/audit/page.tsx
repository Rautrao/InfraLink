'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button, Input, Card, toast, Pagination, Badge } from '@/components/ui';

export default function AuditLog() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ entity: '', entity_id: '' });
  const [verifyResult, setVerifyResult] = useState<{ valid: boolean, broken_at: string | null } | null>(null);

  const qs = new URLSearchParams({ page: page.toString(), ...filters }).toString();
  const { data, isLoading, refetch } = useQuery({ 
    queryKey: ['audit', qs], 
    queryFn: () => api<any>(`/audit?${qs}`) 
  });

  const verifyIntegrity = async () => {
    try {
      const res = await api<any>('/audit/verify');
      setVerifyResult(res);
      if (res.valid) toast('Audit chain intact! ?o+');
      else toast('Tampering detected!');
    } catch (err: any) {
      toast(err.message || 'Verification failed');
    }
  };

  return (
    <div className="max-w-7xl mx-auto flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Audit Log</h1>
        <div className="flex items-center gap-4">
          {verifyResult && (
            <Badge tone={verifyResult.valid ? 'success' : 'critical'}>
              {verifyResult.valid ? '?o+ Chain Intact' : `! Tampered at #${verifyResult.broken_at}`}
            </Badge>
          )}
          <Button onClick={verifyIntegrity} tone="secondary">Verify Integrity</Button>
        </div>
      </div>

      <Card className="p-4 bg-white shadow-sm border border-gray-200">
        <div className="flex gap-4">
          <Input 
            placeholder="Entity (e.g. work, outbox_event)" 
            value={filters.entity} 
            onChange={e => { setFilters({ ...filters, entity: e.target.value }); setPage(1); }} 
          />
          <Input 
            placeholder="Entity ID" 
            value={filters.entity_id} 
            onChange={e => { setFilters({ ...filters, entity_id: e.target.value }); setPage(1); }} 
          />
        </div>
      </Card>

      <Card className="p-0 overflow-hidden">
        <table className="w-full text-left text-sm text-gray-700 font-mono">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="p-3">ID / At</th>
              <th className="p-3">Action</th>
              <th className="p-3">Entity</th>
              <th className="p-3">Actor</th>
              <th className="p-3">Hash</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.items?.map((log: any) => (
              <tr key={log.id} className="hover:bg-gray-50">
                <td className="p-3">
                  <div className="font-bold text-gray-900">#{log.id}</div>
                  <div className="text-xs text-gray-500">{new Date(log.at).toLocaleString()}</div>
                </td>
                <td className="p-3"><Badge tone="neutral">{log.action}</Badge></td>
                <td className="p-3">
                  {log.entity}
                  <div className="text-xs text-gray-500">{log.entity_id}</div>
                </td>
                <td className="p-3 text-xs">{log.actor_id || 'System'}</td>
                <td className="p-3 text-xs max-w-xs truncate" title={log.hash}>
                  {log.hash.substring(0, 16)}...
                </td>
              </tr>
            ))}
            {!data?.items?.length && <tr><td colSpan={5} className="p-4 text-center text-gray-500">No audit logs found.</td></tr>}
          </tbody>
        </table>
        {data && (
          <div className="p-4 border-t bg-gray-50 flex justify-between items-center">
            <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            <div className="text-sm text-gray-500">Total: {data.total} logs</div>
          </div>
        )}
      </Card>
    </div>
  );
}
