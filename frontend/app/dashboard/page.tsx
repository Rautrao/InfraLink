'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Card, Button, Skeleton, EmptyState } from '@/components/ui';
import { Download } from 'lucide-react';
import dynamic from 'next/dynamic';
import Link from 'next/link';

const BarChart = dynamic(() => import("recharts").then(m => m.BarChart), { ssr: false });
const Bar = dynamic(() => import("recharts").then(m => m.Bar), { ssr: false });
const PieChart = dynamic(() => import("recharts").then(m => m.PieChart), { ssr: false });
const Pie = dynamic(() => import("recharts").then(m => m.Pie), { ssr: false });
const Tooltip = dynamic(() => import("recharts").then(m => m.Tooltip), { ssr: false });
const ResponsiveContainer = dynamic(() => import("recharts").then(m => m.ResponsiveContainer), { ssr: false });
const XAxis = dynamic(() => import("recharts").then(m => m.XAxis), { ssr: false });
const YAxis = dynamic(() => import("recharts").then(m => m.YAxis), { ssr: false });

export default function DashboardPage() {
  const { data, isLoading } = useQuery({ queryKey: ['dashboard'], queryFn: () => api<any>('/reports/summary').catch(() => null) });
  
  if (isLoading) return <div className="p-8"><Skeleton className="h-64 mb-4" /></div>;
  if (!data) return <div className="p-8"><EmptyState title="Dashboard data unavailable" /></div>;

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div className="flex justify-between items-center flex-wrap gap-4">
        <h1 className="text-3xl font-bold">Public Accountability Dashboard</h1>
        <div className="flex gap-2">
          <Link href="/api/v1/public_api/works.csv" download>
            <Button tone="secondary"><Download className="w-4 h-4 mr-2 inline" /> CSV</Button>
          </Link>
          <Link href="/api/v1/public_api/works.geojson" download>
            <Button tone="secondary"><Download className="w-4 h-4 mr-2 inline" /> GeoJSON</Button>
          </Link>
        </div>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="p-4 text-center"><h3 className="text-sm text-gray-500">Total Works</h3><div className="text-2xl font-bold">{data.kpi?.total || 0}</div></Card>
        <Card className="p-4 text-center"><h3 className="text-sm text-gray-500">Ongoing</h3><div className="text-2xl font-bold">{data.kpi?.ongoing || 0}</div></Card>
        <Card className="p-4 text-center border-orange-200 bg-orange-50"><h3 className="text-sm text-orange-600">Delayed</h3><div className="text-2xl font-bold text-orange-700">{data.kpi?.delayed || 0}</div></Card>
        <Card className="p-4 text-center border-red-200 bg-red-50"><h3 className="text-sm text-red-600">Updates Overdue</h3><div className="text-2xl font-bold text-red-700">{data.kpi?.update_overdue || 0}</div></Card>
        <Card className="p-4 text-center border-green-200 bg-green-50"><h3 className="text-sm text-green-600">Completed (Month)</h3><div className="text-2xl font-bold text-green-700">{data.kpi?.completed_month || 0}</div></Card>
      </div>
    </div>
  );
}
