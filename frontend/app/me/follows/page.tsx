'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { Button, Card, EmptyState, ErrorState, Skeleton } from '@/components/ui';

type FollowItem = { id: string; work_id: string | null; ward_id: string | null; work_title?: string | null; ward_name?: string | null; channel: string };
type Notification = { id: string; title: string; body: string; link?: string | null; created_at: string; read_at?: string | null; project_name?: string | null; affected_location?: { road_name?: string | null; ward?: string | null } };

export default function MyFollows() {
  const { t, formatDate } = useT();
  const queryClient = useQueryClient();
  const [ready, setReady] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(Boolean(localStorage.getItem('access_token')));
    setReady(true);
  }, []);

  const follows = useQuery({ queryKey: ['my-follows'], enabled: ready && loggedIn, queryFn: () => api<{ items: FollowItem[] }>('/follows') });
  const notifications = useQuery({ queryKey: ['my-notifications'], enabled: ready && loggedIn, queryFn: () => api<{ items: Notification[] }>('/notifications/mine') });
  const unfollow = useMutation({
    mutationFn: (item: FollowItem) => {
      const params = new URLSearchParams(item.work_id ? { work_id: item.work_id } : { ward_id: item.ward_id ?? '' });
      return api(`/follows?${params}`, { method: 'DELETE' });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['my-follows'] }),
  });
  const markRead = useMutation({
    mutationFn: (id: string) => api(`/notifications/${id}/read`, { method: 'PATCH' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['my-notifications'] }),
  });

  if (!ready || (loggedIn && (follows.isLoading || notifications.isLoading))) {
    return <main className="page-wrap page-narrow"><Skeleton className="skeleton-card"/><Skeleton className="skeleton-card"/></main>;
  }

  return <main className="page-wrap page-narrow">
    <h1 className="page-title">{t('myFollowsTitle')}</h1>
    {!loggedIn ? <EmptyState title={t('login')} detail={t('signInToView')} action={<Link className="ui-button ui-button-primary" href="/login?returnTo=%2Fme%2Ffollows">{t('login')}</Link>}/>
      : <div className="grid gap-6 md:grid-cols-2">
        <section className="grid content-start gap-3" aria-labelledby="followed-items-heading">
          <h2 id="followed-items-heading" className="text-xl font-bold">{t('followedItems')}</h2>
          {follows.isError ? <ErrorState onRetry={() => void follows.refetch()}/> : !follows.data?.items.length ? <EmptyState title={t('noFollowedItems')} detail={t('followPromptAction')}/> : follows.data.items.map((item) => {
            const href = item.work_id ? `/works/${item.work_id}` : `/wards/${item.ward_id}`;
            return <Card key={item.id} className="grid gap-3">
              <div><strong>{item.work_id ? item.work_title || t('projectFollow') : item.ward_name || t('wardFollow')}</strong><p className="text-sm text-slate-600">{item.channel}</p></div>
              <div className="flex flex-wrap gap-2"><Link className="ui-button ui-button-secondary" href={href}>{t('openDetails')}</Link><Button tone="quiet" disabled={unfollow.isPending} onClick={() => unfollow.mutate(item)}>{t('removeFollow')}</Button></div>
            </Card>;
          })}
          {unfollow.isError && <ErrorState onRetry={() => unfollow.reset()}/>}
        </section>
        <section className="grid content-start gap-3" aria-labelledby="notifications-heading">
          <h2 id="notifications-heading" className="text-xl font-bold">{t('recentNotifications')}</h2>
          {notifications.isError ? <ErrorState onRetry={() => void notifications.refetch()}/> : !notifications.data?.items.length ? <EmptyState title={t('noNotifications')}/> : notifications.data.items.map((item) =>
            <Card key={item.id} className={`grid gap-2 ${item.read_at ? '' : 'border-l-4 border-l-teal-700'}`}>
              <div className="flex items-start justify-between gap-2"><strong>{item.title}</strong>{!item.read_at && <span className="text-xs font-bold text-teal-800">●</span>}</div>
              {item.project_name && <p className="text-sm font-semibold">{item.project_name}</p>}
              <p className="text-sm text-slate-700">{item.body}</p>
              {(item.affected_location?.road_name || item.affected_location?.ward) && <p className="text-sm text-slate-600">{[item.affected_location.road_name, item.affected_location.ward].filter(Boolean).join(' · ')}</p>}
              <div className="flex items-center justify-between gap-2"><time className="text-xs text-slate-500">{formatDate(item.created_at, { hour: 'numeric', minute: '2-digit' })}</time><div className="flex gap-2">{item.link && <Link className="ui-button ui-button-secondary" href={item.link}>{t('open')}</Link>}{!item.read_at && <Button tone="quiet" disabled={markRead.isPending} onClick={() => markRead.mutate(item.id)}>{t('markRead')}</Button>}</div></div>
            </Card>
          )}
          {markRead.isError && <ErrorState onRetry={() => markRead.reset()}/>}
        </section>
      </div>}
  </main>;
}
