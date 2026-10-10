'use client';
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { api, ApiError } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { Card, Button, Skeleton, EmptyState, ErrorState, StatusChip, toast } from '@/components/ui';
import dynamic from 'next/dynamic';

const MapView = dynamic(() => import('@/components/ui/MapView').then(mod => mod.MapView), { ssr: false, loading: () => <Skeleton className="h-64" /> });
type Ward={id:string;name:string;boundary?:any};
type Works={items?:any[];total?:number};
export default function WardPage({params}:{params:{id:string}}) {
  const {t}=useT();const router=useRouter();const [loggedIn,setLoggedIn]=useState(false);
  useEffect(()=>setLoggedIn(Boolean(localStorage.getItem('access_token'))),[]);
  const wardsQuery=useQuery({queryKey:['wards'],queryFn:()=>api<Ward[]>('/wards')});
  const ward=wardsQuery.data?.find(item=>item.id===params.id||item.name===decodeURIComponent(params.id));
  const worksQuery=useQuery({queryKey:['ward-works',ward?.id],enabled:Boolean(ward?.id),queryFn:()=>api<Works>(`/works?ward_id=${encodeURIComponent(ward!.id)}&page_size=100`) });
  const geo=useQuery({queryKey:['ward-geo',ward?.id],enabled:Boolean(ward?.id),queryFn:()=>api<any>(`/works/geojson?ward_id=${encodeURIComponent(ward!.id)}`)});
  if(wardsQuery.isLoading)return <main className="page-wrap"><Skeleton className="skeleton-card"/></main>;
  if(wardsQuery.isError)return <main className="page-wrap"><ErrorState onRetry={()=>wardsQuery.refetch()}/></main>;
  if(!ward)return <main className="page-wrap"><EmptyState title={t('dashboardUnavailable')}/></main>;
  const works=worksQuery.data?.items??[];const active=works.filter(work=>['planned','permitted','ongoing','paused'].includes(work.status)).length;
  async function follow(){if(!loggedIn){router.push(`/login?returnTo=${encodeURIComponent(`/wards/${params.id}`)}`);return;}try{await api('/follows',{method:'POST',body:JSON.stringify({ward_id:ward!.id,channel:'console'})});toast(t('followed'));}catch(error){if(error instanceof ApiError&&(error.status===401||error.status===403)){router.push(`/login?returnTo=${encodeURIComponent(`/wards/${params.id}`)}`);return;}toast(error instanceof Error?error.message:t('error'));}}
  return <main className="page-wrap space-y-6"><div className="flex justify-between items-center flex-wrap gap-4"><h1 className="page-title">{t('wardTitle')}: {ward.name}</h1><Button onClick={follow}>{t('followWard')}</Button></div><Card className="p-4"><div className="flex gap-8 mb-4"><div><strong className="block text-2xl">{worksQuery.data?.total??works.length}</strong><span className="text-gray-500">{t('totalWorks')}</span></div><div><strong className="block text-2xl">{active}</strong><span className="text-gray-500">{t('activeWorks')}</span></div></div>{geo.isLoading?<Skeleton className="h-64"/>:geo.isError?<ErrorState onRetry={()=>geo.refetch()}/>:<MapView data={geo.data??{type:'FeatureCollection',features:[]}}/>}</Card>{worksQuery.isLoading?<Skeleton className="skeleton-card"/>:worksQuery.isError?<ErrorState onRetry={()=>worksQuery.refetch()}/>:works.length?<div className="work-grid">{works.map(work=><Card key={work.id}><StatusChip status={work.status} label={t(work.status)}/><h2><a href={`/works/${work.id}`}>{work.title}</a></h2><p>{work.road_name}</p></Card>)}</div>:<EmptyState title={t('noRows')}/>}</main>;
}
