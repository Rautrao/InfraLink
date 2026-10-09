'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button, Card, EmptyState, ErrorState, Skeleton } from '@/components/ui';
import Link from 'next/link';

export default function MyFollows() {
  const { data: follows, isLoading, isError, refetch } = useQuery({
    queryKey: ['my-follows'],
    queryFn: () => api<any[]>('/me/follows').catch(() => []) // Mocking empty if 404
  });

  const { data: notifications } = useQuery({
    queryKey: ['my-notifications'],
    queryFn: () => api<any[]>('/notifications/mine').catch(() => []) // Mocking empty if 404
  });

  if (isLoading) return <div className="max-w-4xl mx-auto p-4"><Skeleton className="h-32 mb-4" /></div>;
  if (isError) return <div className="max-w-4xl mx-auto p-4"><ErrorState onRetry={() => refetch()} /></div>;

  return (
    <div className="max-w-4xl mx-auto p-4 flex flex-col gap-6 pb-20">
      <h1 className="text-2xl font-bold">My Follows & Alerts</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="flex flex-col gap-4">
          <h2 className="text-xl font-bold border-b pb-2">Followed Items</h2>
          {!follows || follows.length === 0 ? (
            <EmptyState title="Not following anything" detail="Click the Follow button on any project or ward." />
          ) : (
            follows.map((follow: any) => (
              <Card key={follow.id} className="p-4 flex justify-between items-center">
                <div>
                  <div className="font-medium">{follow.work_id ? 'Project Follow' : 'Ward Follow'}</div>
                  <Link href={follow.work_id ? `/works/${follow.work_id}` : `/wards/${follow.ward_id}`} className="text-sm text-blue-600 hover:underline">
                    View Details
                  </Link>
                </div>
                <div className="text-xs bg-gray-100 p-1 rounded">{follow.channel}</div>
              </Card>
            ))
          )}
        </div>

        <div className="flex flex-col gap-4">
          <h2 className="text-xl font-bold border-b pb-2">Recent Notifications</h2>
          {!notifications || notifications.length === 0 ? (
            <EmptyState title="No recent notifications" />
          ) : (
            notifications.map((n: any) => (
              <Card key={n.id} className="p-4 border-l-4 border-blue-500">
                <div className="font-bold text-sm text-blue-800">{n.title}</div>
                <div className="text-sm text-gray-700 mt-1">{n.body}</div>
                <div className="text-xs text-gray-500 mt-2 flex justify-between">
                  <span>{new Date(n.created_at).toLocaleString()}</span>
                  {n.link && <Link href={n.link} className="text-blue-600 hover:underline">Open</Link>}
                </div>
              </Card>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
