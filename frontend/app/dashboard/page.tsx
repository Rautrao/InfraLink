'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { Card, Button, Skeleton, EmptyState, ErrorState } from '@/components/ui';
import { Download } from 'lucide-react';

type Summary={total:number;ongoing:number;delayed:number;overdue_updates:number;completed_this_month:number};
const apiBase=process.env.NEXT_PUBLIC_API_BASE??'/api/v1';
export default function DashboardPage() {
  const {t}=useT();
  const query=useQuery({queryKey:['dashboard'],queryFn:()=>api<Summary>('/reports/summary')});
  if(query.isLoading)return <main className="page-wrap"><Skeleton className="skeleton-card"/></main>;
  if(query.isError)return <main className="page-wrap"><ErrorState onRetry={()=>query.refetch()}/></main>;
  const data=query.data;
  if(!data)return <main className="page-wrap"><EmptyState title={t('dashboardUnavailable')}/></main>;
  const cards=[[t('totalWorks'),data.total,''],[t('ongoing'),data.ongoing,''],[t('delayed'),data.delayed,'border-orange-200 bg-orange-50'],[t('updateOverdue'),data.overdue_updates,'border-red-200 bg-red-50'],[t('completedThisMonth'),data.completed_this_month,'border-green-200 bg-green-50']];
  return <main className="page-wrap space-y-8"><div className="flex justify-between items-center flex-wrap gap-4"><h1 className="page-title">{t('publicDashboard')}</h1><div className="flex gap-2"><a href={`${apiBase}/open/works.csv`}><Button tone="secondary"><Download className="w-4 h-4 mr-2 inline"/>CSV</Button></a><a href={`${apiBase}/open/works.geojson`}><Button tone="secondary"><Download className="w-4 h-4 mr-2 inline"/>GeoJSON</Button></a></div></div><div className="grid grid-cols-2 md:grid-cols-5 gap-4">{cards.map(([label,value,tone])=><Card key={label} className={`p-4 text-center ${tone}`}><h2 className="text-sm text-gray-500">{label}</h2><div className="text-2xl font-bold">{value}</div></Card>)}</div></main>;
}
