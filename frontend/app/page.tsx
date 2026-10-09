'use client';
import { FormEvent, useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { Button, Card, ErrorState, Input, Skeleton } from '@/components/ui';

type Summary={by_status?:Record<string,number>;delayed_count?:number;completed_this_month?:number;last_updated_at?:string};
export default function Home(){
  const {t}=useT();const [search,setSearch]=useState('');
  const summary=useQuery({queryKey:['summary'],queryFn:()=>api<Summary>('/reports/summary')});
  function submit(event:FormEvent){event.preventDefault();window.location.href=`/works?${new URLSearchParams({q:search.trim()})}`;}
  const stats=summary.data;
  return <main className="page-wrap"><section className="home-hero"><div className="hero-content"><span className="eyebrow">Demo City · Pune</span><h1 className="page-title hero-title">{t('brand')}</h1><p className="page-lede">{t('heroDescription')}</p><form className="hero-search" onSubmit={submit}><Input aria-label={t('search')} placeholder={t('searchHint')} value={search} onChange={e=>setSearch(e.target.value)}/><Button type="submit">⌕ {t('works')}</Button></form><div className="link-row" style={{marginTop:16}}><Link className="ui-button ui-button-primary" href="/works?view=map">{t('viewMap')} →</Link><Link className="ui-button ui-button-secondary" href="/works?view=list">{t('viewList')} →</Link></div></div></section>
    <section aria-label={t('cityGlance')}><div className="section-head"><div><h2>{t('cityGlance')}</h2><p>{t('citySummary')}</p></div></div>{summary.isLoading?<div className="quick-stats">{[1,2,3].map(i=><Skeleton key={i} className="skeleton-card"/>)}</div>:summary.isError?<Card><ErrorState onRetry={()=>summary.refetch()}/></Card>:<div className="quick-stats"><Card className="stat-card"><span className="stat-icon stat-current">{t('ongoing')}</span><strong>{stats?.by_status?.ongoing??0}</strong><span>{t('ongoingWorks')}</span></Card><Card className="stat-card"><span className="stat-icon stat-delay">{t('delayed')}</span><strong>{stats?.delayed_count??0}</strong><span>{t('pastTargetWork')}</span></Card><Card className="stat-card"><span className="stat-icon">{t('completedMonth')}</span><strong>{stats?.completed_this_month??stats?.by_status?.completed??0}</strong><span>{t('completedMonth')}</span></Card></div>}</section>
    <section className="section-head"><div><h2>{t('followCity')}</h2><p>{t('checkProgress')}</p></div><Link href="/works" className="ui-button ui-button-secondary">{t('viewList')} →</Link></section>
  </main>;
}
