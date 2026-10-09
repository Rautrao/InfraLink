'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Card, Button, Skeleton, EmptyState } from '@/components/ui';
import dynamic from 'next/dynamic';

const MapView = dynamic(() => import("@/components/ui/MapView").then(mod => mod.MapView), { ssr: false, loading: () => <Skeleton className="h-64" /> });

export default function WardPage({ params }: { params: { id: string } }) {
  const { data, isLoading } = useQuery({ queryKey: ['ward', params.id], queryFn: () => api<any>(`/wards/${params.id}`).catch(() => null) });
  
  if (isLoading) return <div className="p-8"><Skeleton className="h-64 mb-4" /></div>;
  if (!data) return <div className="p-8"><EmptyState title="Ward data unavailable" /></div>;

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Ward: {data.name || params.id}</h1>
        <Button onClick={() => api('/follows', { method: 'POST', body: JSON.stringify({ ward_id: params.id, channel: 'console' }) })}>
          Follow this Ward
        </Button>
      </div>
      <Card className="p-4">
        <div className="flex gap-8 mb-4">
          <div><strong className="block text-2xl">{data.counts?.total || 0}</strong><span className="text-gray-500">Total Works</span></div>
          <div><strong className="block text-2xl">{data.counts?.active || 0}</strong><span className="text-gray-500">Active</span></div>
        </div>
        <MapView data={data.geojson || { type: 'FeatureCollection', features: [] }} />
      </Card>
    </div>
  );
}
