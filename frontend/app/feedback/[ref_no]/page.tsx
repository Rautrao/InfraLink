'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { useT } from '@/lib/i18n';
import { api } from '@/lib/api';
import { Badge, Card, EmptyState, ErrorState, Skeleton, StatusChip, Timeline } from '@/components/ui';

type Ticket = {
  id: string; ref_no: string; work_id: string; work_title: string; kind: string; text: string;
  status: string; current_level: number; created_at: string; photo_url?: string | null;
  history: { id: string; status: string; message?: string | null; at: string; is_public: boolean }[];
};

export default function TicketDetail({ params }: { params: { ref_no: string } }) {
  const { t, formatDate } = useT();
  const [ready, setReady] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [photoSrc, setPhotoSrc] = useState('');
  useEffect(() => {
    setLoggedIn(Boolean(localStorage.getItem('access_token')));
    setReady(true);
  }, []);
  const query = useQuery({
    queryKey: ['feedback', params.ref_no],
    enabled: ready && loggedIn,
    queryFn: () => api<Ticket>(`/feedback/${encodeURIComponent(params.ref_no)}`),
  });
  const ticket = query.data;

  useEffect(() => {
    if (!ticket?.photo_url) return;
    const token = localStorage.getItem('access_token');
    const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000/api/v1';
    const photoUrl = new URL(ticket.photo_url, apiBase).toString();
    let objectUrl = '';
    let cancelled = false;
    void fetch(photoUrl, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((response) => { if (!response.ok) throw new Error('Photo unavailable'); return response.blob(); })
      .then((blob) => { objectUrl = URL.createObjectURL(blob); if (!cancelled) setPhotoSrc(objectUrl); })
      .catch(() => setPhotoSrc(''));
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [ticket?.photo_url]);

  if (!ready || (loggedIn && query.isLoading)) return <main className="page-wrap page-narrow"><Skeleton className="skeleton-card"/></main>;
  if (!loggedIn) return <main className="page-wrap page-narrow"><EmptyState title={t('login')} detail={t('signInToView')} action={<Link className="ui-button ui-button-primary" href={`/login?returnTo=${encodeURIComponent(`/feedback/${params.ref_no}`)}`}>{t('login')}</Link>}/></main>;
  if (query.isError || !ticket) return <main className="page-wrap page-narrow"><ErrorState onRetry={() => void query.refetch()}/></main>;

  const timeline = [...ticket.history].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime()).map((event) => ({
    id: event.id,
    title: t(event.status),
    detail: event.message || undefined,
    date: event.at,
    by: event.is_public ? t('publicResponse') : t('statusUpdate'),
  }));
  const firstResponse = new Date(ticket.created_at);
  firstResponse.setDate(firstResponse.getDate() + 3);

  return <main className="page-wrap page-narrow grid gap-5">
    <header className="grid gap-2 border-b border-slate-200 pb-4">
      <span className="font-mono font-bold text-teal-800">{ticket.ref_no}</span>
      <h1 className="page-title">{t('ticketDetails')}</h1>
      <div className="flex flex-wrap items-center gap-2"><StatusChip status={ticket.status} label={t(ticket.status)}/><Badge>{t(ticket.kind)}</Badge>{ticket.current_level > 1 && <Badge tone="warning">{t('escalatedLevel').replace('{level}', String(ticket.current_level))}</Badge>}</div>
      <p className="whitespace-pre-wrap rounded-xl bg-white p-4">{ticket.text}</p>
      {photoSrc && <img src={photoSrc} alt={t('attachedFeedbackPhoto')} className="max-h-96 w-fit rounded-xl border"/>}
      <Link href={`/works/${ticket.work_id}`} className="font-semibold">{ticket.work_title} · {t('openDetails')}</Link>
    </header>
    <Card><h2 className="mb-4 text-xl font-bold">{t('resolutionTimeline')}</h2>{timeline.length ? <Timeline items={timeline}/> : <EmptyState title={t('noHistory')}/>}</Card>
    <Card className="bg-teal-50"><h2 className="font-bold">{t('serviceLevel')}</h2><p className="text-sm">{t('firstResponseBy')}: <strong>{formatDate(firstResponse.toISOString())}</strong></p></Card>
  </main>;
}
