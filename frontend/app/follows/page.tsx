'use client';
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { Card, EmptyState, ErrorState, LastUpdated, Skeleton, StatusChip } from '@/components/ui';
type Follows={items:{id:string;work?:{id:string;title:string;status:string;road_name?:string;last_update_at?:string};work_id?:string}[]};
export default function Follows(){const {t}=useT();const [ready,setReady]=useState(false);const [loggedIn,setLoggedIn]=useState(false);useEffect(()=>{setLoggedIn(Boolean(localStorage.getItem('access_token')));setReady(true);},[]);const query=useQuery({queryKey:['my-follows'],enabled:loggedIn,queryFn:()=>api<Follows>('/follows/mine')});if(!ready||query.isLoading&&loggedIn)return <main className="page-wrap"><Skeleton className="skeleton-card"/></main>;if(!loggedIn)return <main className="page-wrap"><EmptyState title={t('login')} detail={t('signInToFollow')} action={<Link className="ui-button ui-button-primary" href="/login?next=%2Ffollows">{t('login')}</Link>}/></main>;if(query.isError)return <main className="page-wrap"><ErrorState onRetry={()=>query.refetch()}/></main>;return <main className="page-wrap"><h1 className="page-title">{t('follows')}</h1>{!query.data?.items?.length?<Card><EmptyState title={t('noFollows')} detail={t('followPrompt')}/></Card>:<div className="work-grid">{query.data.items.map(item=>{const work=item.work;if(!work)return null;return <Card key={item.id}><StatusChip status={work.status} label={t(work.status as any)}/><h2><Link href={`/works/${work.id}`}>{work.title}</Link></h2><p>{work.road_name}</p><LastUpdated value={work.last_update_at}/></Card>;})}</div>}</main>;}
