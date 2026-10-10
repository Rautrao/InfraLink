'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { Badge, Button, Card, EmptyState, ErrorState, LastUpdated, Skeleton, StatusChip } from '@/components/ui';

type Ticket = { id: string; ref_no: string; work_id?: string; work_title?: string; kind: string; text: string; status: string; current_level: number; created_at: string; last_response_at?: string | null };

export default function MyFeedback() {
  const { t } = useT();
  const [ready, setReady] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  useEffect(() => {
    setLoggedIn(Boolean(localStorage.getItem('access_token')));
    setReady(true);
  }, []);

  const query = useQuery({
    queryKey: ['my-feedback'],
    enabled: ready && loggedIn,
    queryFn: () => api<{ items: Ticket[] }>('/feedback/mine'),
  });

  if (!ready || (loggedIn && query.isLoading)) return <main className="page-wrap page-narrow"><Skeleton className="skeleton-card"/><Skeleton className="skeleton-card"/></main>;
  return <main className="page-wrap page-narrow">
    <h1 className="page-title">{t('feedbackTitlePage')}</h1>
    {!loggedIn ? <EmptyState title={t('login')} detail={t('signInToView')} action={<Link className="ui-button ui-button-primary" href="/login?returnTo=%2Fme%2Ffeedback">{t('login')}</Link>}/>
      : query.isError ? <ErrorState onRetry={() => void query.refetch()}/>
      : !query.data?.items.length ? <EmptyState title={t('noFeedback')} detail={t('feedbackPrompt')}/>
      : <div className="grid gap-4">{query.data.items.map((ticket) => <Card key={ticket.id} className="grid gap-3">
        <div className="flex flex-wrap items-center gap-2"><span className="font-mono font-bold text-teal-800">{ticket.ref_no}</span><StatusChip status={ticket.status}/><Badge>{t(ticket.kind)}</Badge>{ticket.current_level > 1 && <Badge tone="warning">{t('escalatedLevel').replace('{level}', String(ticket.current_level))}</Badge>}</div>
        <p className="line-clamp-3">{ticket.text}</p>
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
          {ticket.work_id ? <Link href={`/works/${ticket.work_id}`} className="font-semibold">{ticket.work_title || t('linkedProject')}</Link> : <span>{t('generalFeedback')}</span>}
          <LastUpdated value={ticket.last_response_at || ticket.created_at}/>
        </div>
        <Link href={`/feedback/${encodeURIComponent(ticket.ref_no)}`}><Button tone="secondary">{t('openDetails')}</Button></Link>
      </Card>)}</div>}
  </main>;
}
