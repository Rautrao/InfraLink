'use client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { I18nProvider } from '@/lib/i18n';
import { ToastProvider } from '@/components/ui';
import { LowBandwidthProvider } from '@/lib/preferences';
export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } } }));
  return <QueryClientProvider client={client}><I18nProvider><LowBandwidthProvider><ToastProvider>{children}</ToastProvider></LowBandwidthProvider></I18nProvider></QueryClientProvider>;
}
