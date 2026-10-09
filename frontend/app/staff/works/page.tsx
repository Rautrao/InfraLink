'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import Link from 'next/link';
import { Button, Input, Select, Badge, StatusChip, Card, Pagination, EmptyState, ErrorState, LastUpdated } from '@/components/ui';

export default function WorksList() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ ward_id: '', status: '', agency_id: '', delayed: '', q: '', overdue: '' });

  const { data: config } = useQuery({ queryKey: ['config-public'], queryFn: () => api<any>('/config/public') });
  const { data: wards } = useQuery({ queryKey: ['wards'], queryFn: () => api<any[]>('/wards') });
  const { data: agencies } = useQuery({ queryKey: ['agencies'], queryFn: () => api<any[]>('/agencies') });
  
  // Also get the current user so we can default to "My works" if applicable
  const { data: user } = useQuery({ queryKey: ['auth-me'], queryFn: () => api<any>('/auth/me') });

  // Build query string
  const queryObj = { ...filters, page: page.toString() };
  // Clean empty filters
  Object.keys(queryObj).forEach(key => !queryObj[key as keyof typeof queryObj] && delete queryObj[key as keyof typeof queryObj]);
  const qs = new URLSearchParams(queryObj).toString();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['works', qs],
    queryFn: () => api<any>(`/works?${qs}`),
    enabled: !!user // Wait until we have user context
  });

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1);
  };

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Works Registry</h1>
        <Link href="/staff/works/new">
          <Button>+ New Work</Button>
        </Link>
      </div>

      <Card className="p-4 bg-white shadow-sm border border-gray-200">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <Input 
            placeholder="Search ref, title..." 
            value={filters.q} 
            onChange={e => handleFilterChange('q', e.target.value)} 
          />
          <Select value={filters.ward_id} onChange={e => handleFilterChange('ward_id', e.target.value)}>
            <option value="">All Wards</option>
            {wards?.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}
          </Select>
          <Select value={filters.agency_id} onChange={e => handleFilterChange('agency_id', e.target.value)}>
            <option value="">All Agencies</option>
            {agencies?.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </Select>
          <Select value={filters.status} onChange={e => handleFilterChange('status', e.target.value)}>
            <option value="">All Statuses</option>
            {config?.statuses?.map((s: string) => <option key={s} value={s}>{s}</option>)}
          </Select>
          <Select value={filters.delayed} onChange={e => handleFilterChange('delayed', e.target.value)}>
            <option value="">Any Timing</option>
            <option value="true">Delayed</option>
          </Select>
          <Select value={filters.overdue} onChange={e => handleFilterChange('overdue', e.target.value)}>
            <option value="">Updates</option>
            <option value="true">Overdue</option>
          </Select>
        </div>
      </Card>

      {isLoading ? (
        <div className="p-12 text-center text-gray-500">Loading works...</div>
      ) : error ? (
        <ErrorState onRetry={() => refetch()} />
      ) : !data?.items?.length ? (
        <EmptyState title="No works found" detail="Adjust filters or create a new work." />
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <table className="w-full text-left text-sm text-gray-700">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="p-4 font-semibold">Ref & Title</th>
                <th className="p-4 font-semibold">Status</th>
                <th className="p-4 font-semibold">Location</th>
                <th className="p-4 font-semibold">Target End</th>
                <th className="p-4 font-semibold">Flags</th>
                <th className="p-4 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {data.items.map((work: any) => (
                <tr key={work.id} className="hover:bg-gray-50 transition-colors">
                  <td className="p-4">
                    <Link href={`/staff/works/${work.id}`} className="block">
                      <div className="font-mono text-xs text-blue-600 mb-1">{work.ref_no}</div>
                      <div className="font-medium text-gray-900">{work.title}</div>
                      <div className="text-xs text-gray-500 mt-1">{work.category.replace('_', ' ')}</div>
                    </Link>
                  </td>
                  <td className="p-4">
                    <StatusChip status={work.status} />
                    <div className="mt-2 text-xs text-gray-500">{work.pct_complete}% complete</div>
                  </td>
                  <td className="p-4">
                    <div className="font-medium">{work.ward?.name || 'Unknown Ward'}</div>
                    <div className="text-xs text-gray-500 mt-1">{work.agency?.name}</div>
                  </td>
                  <td className="p-4 text-gray-600">
                    {work.current_target_end}
                  </td>
                  <td className="p-4 flex flex-col gap-1 items-start">
                    {work.delayed && <Badge tone="critical">Delayed</Badge>}
                    {work.update_overdue && <Badge tone="warning">Update Overdue</Badge>}
                    {!work.delayed && !work.update_overdue && <span className="text-gray-400 text-xs">-</span>}
                  </td>
                  <td className="p-4">
                    <Link href={`/staff/works/${work.id}`}>
                      <Button tone="secondary" className="text-xs py-1 px-2">Manage</Button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="p-4 border-t border-gray-200 flex justify-between items-center bg-gray-50">
            <Pagination 
              page={page} 
              pageSize={data.page_size || 20} 
              total={data.total || 0} 
              onPage={setPage} 
            />
            <div className="text-sm text-gray-500">Total: {data.total} works</div>
          </div>
        </div>
      )}
    </div>
  );
}
