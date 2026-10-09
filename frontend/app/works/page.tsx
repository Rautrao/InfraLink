'use client';

import { Suspense, FormEvent, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { usePreferences } from '@/lib/preferences';
import { Badge, Button, Card, Drawer, EmptyState, ErrorState, Input, LastUpdated, MapView, Pagination, Select, Skeleton, StatusChip, Tabs, WorkFeature } from '@/components/ui';
import type { FeatureCollection, Geometry } from 'geojson';

type Work={id:string;ref_no?:string;title:string;purpose?:string;status:string;delayed?:boolean;update_overdue?:boolean;agency?:{id?:string;name:string};contractor_name?:string|null;road_name?:string;ward?:{id:string;name:string};category?:string;planned_start?:string;original_target_end?:string;current_target_end?:string;last_update_at?:string;geometry?:Geometry;pct_complete?:number;[key:string]:any};
type WorkPage={items:Work[];total:number;page:number;page_size:number};
type Filters={road:string;ward:string;category:string;agency:string;status:string;q:string;delayed:string};
const emptyFilters:Filters={road:'',ward:'',category:'',agency:'',status:'',q:'',delayed:''};
const categories=['road_cut','resurfacing','water_pipeline','sewer','drainage','electricity','telecom_duct','gas_pipeline','metro','footpath','other'];
const statuses=['planned','permitted','ongoing','paused','completed','restoration_verified','delayed'];
function filtersFrom(params:URLSearchParams):Filters{return{road:params.get('road')??'',ward:params.get('ward_id')??'',category:params.get('category')??'',agency:params.get('agency_id')??'',status:params.get('status')??'',q:params.get('q')??'',delayed:params.get('delayed')??''};}
function center(feature:WorkFeature):[number,number]{const points:number[][]=[];const visit=(v:any)=>{if(!Array.isArray(v))return;if(typeof v[0]==='number')points.push(v);else v.forEach(visit);};if(feature.geometry)visit((feature.geometry as any).coordinates);return points.length?[points.reduce((s,p)=>s+p[0],0)/points.length,points.reduce((s,p)=>s+p[1],0)/points.length]:[73.8567,18.5204];}
function distance(a:[number,number],b:[number,number]){const rad=(d:number)=>d*Math.PI/180;const dLat=rad(b[1]-a[1]),dLon=rad(b[0]-a[0]);const x=Math.sin(dLat/2)**2+Math.cos(rad(a[1]))*Math.cos(rad(b[1]))*Math.sin(dLon/2)**2;return 6371000*2*Math.atan2(Math.sqrt(x),Math.sqrt(1-x));}

function WorksPage(){
  const {t,formatDate}=useT();const {lowBandwidth}=usePreferences();const router=useRouter();const pathname=usePathname();const searchParams=useSearchParams();
  const paramsKey=searchParams.toString();const params=new URLSearchParams(paramsKey);const filters=filtersFrom(params);const view=params.get('view')==='list'?'list':'map';const page=Math.max(1,Number(params.get('page')||1));const [drawer,setDrawer]=useState(false);const [draft,setDraft]=useState(filters);const [bbox,setBbox]=useState(params.get('bbox')??'');const [near,setNear]=useState<[number,number]|null>(null);const [selected,setSelected]=useState<WorkFeature|null>(null);const [fitToken,setFitToken]=useState(0);
  useEffect(()=>setDraft(filters),[paramsKey]);
  const queryParams=new URLSearchParams();
  if(filters.ward)queryParams.set('ward_id',filters.ward);if(filters.road)queryParams.set('road',filters.road);if(filters.category)queryParams.set('category',filters.category);if(filters.agency)queryParams.set('agency_id',filters.agency);if(filters.status&&filters.status!=='delayed')queryParams.set('status',filters.status);if(filters.q)queryParams.set('q',filters.q);if(filters.delayed||filters.status==='delayed')queryParams.set('delayed','true');
  const queryKey=queryParams.toString();
  const workQuery=useQuery({queryKey:['works',queryKey],queryFn:()=>api<WorkPage>(`/works?${queryKey}${queryKey?'&':''}page=1&page_size=100`)});
  const geoQuery=useQuery({queryKey:['works-geojson',queryKey,bbox],queryFn:()=>api<FeatureCollection<Geometry,any>>(`/works/geojson?${queryKey}${queryKey?'&':''}${bbox?`bbox=${bbox}&`:''}page_size=100`)});
  const works=workQuery.data?.items??[];
  const filtered=useMemo(()=>works.filter(w=>{
    if(filters.ward&&w.ward?.id!==filters.ward)return false;
    if(filters.road&&!w.road_name?.toLowerCase().includes(filters.road.toLowerCase()))return false;
    if(filters.category&&w.category!==filters.category)return false;
    if(filters.agency&&w.agency?.id!==filters.agency)return false;
    if(filters.status==='delayed'&&!w.delayed)return false;
    if(filters.status&&filters.status!=='delayed'&&w.status!==filters.status)return false;
    if((filters.delayed||filters.status==='delayed')&&!w.delayed)return false;
    const q=filters.q.trim().toLowerCase();if(q&&!`${w.title} ${w.road_name??''} ${w.ref_no??''} ${w.ward?.name??''}`.toLowerCase().includes(q))return false;
    return true;
  }),[works,filters]);
  const pageSize=6;const maxPage=Math.max(1,Math.ceil(filtered.length/pageSize));const currentPage=Math.min(page,maxPage);
  const pageItems=useMemo(()=>{const rows=[...filtered];if(near)rows.sort((a,b)=>distance(near,center({geometry:a.geometry,properties:{},type:'Feature'} as WorkFeature))-distance(near,center({geometry:b.geometry,properties:{},type:'Feature'} as WorkFeature)));return rows.slice((currentPage-1)*pageSize,currentPage*pageSize);},[filtered,currentPage,near]);
  const visibleIds=new Set(filtered.map(work=>work.id));
  const features=(geoQuery.data?.features??[]).filter((feature:any)=>{
    if(!visibleIds.has(String(feature.id??feature.properties?.id)))return false;
    const p=feature.properties??{};if(filters.category&&p.category!==filters.category)return false;if(filters.status==='delayed'&&!p.delayed)return false;if(filters.status&&filters.status!=='delayed'&&p.status!==filters.status)return false;if((filters.delayed||filters.status==='delayed')&&!p.delayed)return false;
    if(filters.q&&!`${p.title??''} ${p.ref_no??''} ${p.agency??''}`.toLowerCase().includes(filters.q.toLowerCase()))return false;
    return true;
  });
  const geoData=(geoQuery.data?{...geoQuery.data,features}: {type:'FeatureCollection',features:[]}) as FeatureCollection<Geometry,any>;
  const wards=Array.from(new Map(works.filter(w=>w.ward).map(w=>[w.ward!.id,w.ward!.name])).entries());const agencies=Array.from(new Map(works.filter(w=>w.agency).map(w=>[w.agency!.id??w.agency!.name,w.agency!.name])).entries());
  const lastUpdated=works.map(w=>w.last_update_at).filter(Boolean).sort().at(-1);
  const statusLabel=(status:string)=>status==='delayed'?t('delayed'):(t(status as any)??status.replaceAll('_',' '));
  const updateUrl=(next:URLSearchParams)=>router.replace(`${pathname}?${next.toString()}`,{scroll:false});
  function apply(event?:FormEvent){event?.preventDefault();const next=new URLSearchParams(paramsKey);for(const [key,value] of Object.entries(draft)){const param=key==='ward'?'ward_id':key==='agency'?'agency_id':key;if(value)next.set(param,value);else next.delete(param);}next.delete('page');setFitToken(n=>n+1);updateUrl(next);setDrawer(false);}
  function reset(){setDraft(emptyFilters);const next=new URLSearchParams(paramsKey);['road','ward_id','category','agency_id','status','q','delayed','page','bbox'].forEach(k=>next.delete(k));updateUrl(next);setBbox('');setNear(null);}
  function setPage(nextPage:number){const next=new URLSearchParams(paramsKey);if(nextPage>1)next.set('page',String(nextPage));else next.delete('page');updateUrl(next);}
  function onNear(){navigator.geolocation?.getCurrentPosition(pos=>setNear([pos.coords.longitude,pos.coords.latitude]),()=>{});}
  function onMapBounds(value:string){setBbox(value);const next=new URLSearchParams(paramsKey);next.set('bbox',value);if(next.toString()!==paramsKey)updateUrl(next);}
  const filterForm=<form onSubmit={apply}><h2>{t('filters')}</h2><div className="form-field"><label className="form-label" htmlFor="road-filter">{t('road')}</label><Input id="road-filter" value={draft.road} onChange={e=>setDraft({...draft,road:e.target.value})} placeholder={t('roadPlaceholder')}/></div><div className="form-field"><label className="form-label" htmlFor="ward-filter">{t('ward')}</label><Select id="ward-filter" value={draft.ward} onChange={e=>setDraft({...draft,ward:e.target.value})}><option value="">{t('allWards')}</option>{wards.map(([id,name])=><option key={id} value={id}>{name}</option>)}</Select></div><div className="form-field"><label className="form-label" htmlFor="category-filter">{t('category')}</label><Select id="category-filter" value={draft.category} onChange={e=>setDraft({...draft,category:e.target.value})}><option value="">{t('allCategories')}</option>{categories.map(c=><option key={c} value={c}>{t('cat_'+c as any)}</option>)}</Select></div><div className="form-field"><label className="form-label" htmlFor="agency-filter">{t('agency')}</label><Select id="agency-filter" value={draft.agency} onChange={e=>setDraft({...draft,agency:e.target.value})}><option value="">{t('allAgencies')}</option>{agencies.map(([id,name])=><option key={id} value={id}>{name}</option>)}</Select></div><div className="form-field"><label className="form-label" htmlFor="status-filter">{t('status')}</label><Select id="status-filter" value={draft.status} onChange={e=>setDraft({...draft,status:e.target.value})}><option value="">{t('allStatuses')}</option>{statuses.map(status=><option key={status} value={status}>{statusLabel(status)}</option>)}</Select></div><div className="form-field"><label className="form-label" htmlFor="keyword-filter">{t('keyword')}</label><Input id="keyword-filter" value={draft.q} onChange={e=>setDraft({...draft,q:e.target.value})} placeholder={t('searchHint')}/></div><label className="filter-check"><input type="checkbox" checked={Boolean(draft.delayed)} onChange={e=>setDraft({...draft,delayed:e.target.checked?'true':''})}/>{t('delayedOnly')}</label><div className="filter-actions"><Button type="submit">{t('apply')}</Button><Button type="button" tone="secondary" onClick={reset}>{t('clear')}</Button></div></form>;

  return <main className="page-wrap"><div className="section-head"><div><span className="eyebrow">{t('cityName')}</span><h1 className="page-title">{t('works')}</h1><p>{t('searchHint')}</p></div><div className="map-tools"><Button className="mobile-filter" tone="secondary" onClick={()=>setDrawer(true)}>☷ {t('filters')}</Button><Button tone="secondary" onClick={onNear}>◎ {t('nearMe')}</Button><Tabs items={[{id:'map',label:`⌖ ${t('map')}`},{id:'list',label:`▤ ${t('list')}`}] as const} value={view} onChange={id=>{const next=new URLSearchParams(paramsKey);next.set('view',id);updateUrl(next);}}/></div></div>
    <div className="last-updated-row"><LastUpdated value={lastUpdated}/></div>
    <div className="work-layout"><Card className="filter-panel">{filterForm}</Card><div>
      {workQuery.isLoading?<div className="work-grid">{[1,2,3,4].map(x=><Skeleton key={x} className="skeleton-card"/>)}</div>:workQuery.isError?<Card><ErrorState onRetry={()=>workQuery.refetch()}/></Card>:filtered.length===0?<Card><EmptyState title={t('noWorks')} detail={t('tryFilters')} action={<Button tone="secondary" onClick={reset}>{t('clear')}</Button>}/></Card>:<>
      {view==='map'&&!lowBandwidth&&<div className="map-area"><MapView data={geoData} fitToken={fitToken} onBoundsChange={onMapBounds} onSelect={feature=>setSelected(feature)}/>{selected&&<div className="map-preview"><Button tone="quiet" style={{float:'right',padding:3,minHeight:32}} aria-label={t('close')} onClick={()=>setSelected(null)}>×</Button><StatusChip status={selected.properties?.delayed?'delayed':selected.properties?.status??'planned'} label={statusLabel(selected.properties?.delayed?'delayed':selected.properties?.status??'planned')}/><h3>{selected.properties?.title}</h3><p>{selected.properties?.agency}</p><LastUpdated value={selected.properties?.last_update_at as string}/><p><Link href={`/works/${selected.properties?.id??selected.id}`}>{t('viewDetails')} →</Link></p></div>}</div>}
      {lowBandwidth&&view==='map'&&<Card className="low-data-note"><p>{t('noMap')}</p><Button tone="secondary" onClick={()=>{const next=new URLSearchParams(paramsKey);next.set('view','list');updateUrl(next);}}>{t('viewList')}</Button></Card>}
      <div className="work-toolbar"><p>{t('resultsCount').replace('{count}',String(filtered.length))}{near?' · '+t('sortedByDistance'):''}</p><div className="map-tools"><Button tone="quiet" onClick={()=>{setSelected(null);setFitToken(n=>n+1);}}>{t('reset')}</Button><Button tone="secondary" className="desktop-only" onClick={()=>setDrawer(true)}>☷ {t('filters')}</Button></div></div>
      {view==='list'||lowBandwidth?<div className="work-grid">{pageItems.map(work=><WorkCard key={work.id} work={work} statusLabel={statusLabel}/>)}</div>:<p className="map-caption">{t('selectMapHint')}</p>}
      {(view==='list'||lowBandwidth)&&<Pagination page={currentPage} pageSize={pageSize} total={filtered.length} onPage={setPage}/>}
      </>}
    </div></div>
    <Drawer open={drawer} title={t('filters')} onClose={()=>setDrawer(false)}><div className="filter-drawer">{filterForm}</div></Drawer>
  </main>;
}
function WorkCard({work,statusLabel}:{work:Work;statusLabel:(status:string)=>string}){const {t,formatDate}=useT();return <Card className="work-card"><div className="status-summary"><StatusChip status={work.delayed?'delayed':work.status} label={statusLabel(work.delayed?'delayed':work.status)}/>{work.update_overdue&&<Badge tone="warning">! Update overdue</Badge>}</div><h3><Link href={`/works/${work.id}`}>{work.title}</Link></h3><p>{work.road_name??'Demo City'} · {work.ward?.name??'Ward'}</p><p>{work.agency?.name}</p><p>{t('plannedStart')}: {formatDate(work.planned_start)} · {t('revisedTarget')}: {formatDate(work.current_target_end)}</p><LastUpdated value={work.last_update_at}/><div className="card-footer"><span>{work.pct_complete??0}% {t('progress').toLowerCase()}</span><Link href={`/works/${work.id}`}>{t('viewDetails')} →</Link></div></Card>}

export default function Page(){return <Suspense fallback={<main className="page-wrap"><Skeleton className="skeleton-card"/></main>}><WorksPage/></Suspense>;}
