import type { Metadata, Viewport } from 'next';

export const metadata: Metadata = {
  title: 'Field Operations PWA | InfraLink',
  description: 'Mobile offline-first field engineer and contractor portal for road works, progress tracking, and restoration verification.',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'InfraLink Field',
  },
};

export const viewport: Viewport = {
  themeColor: '#075e67',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function FieldLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="field-pwa-container min-h-[calc(100vh-68px)] bg-slate-50 text-slate-900 pb-12 antialiased">
      {children}
    </div>
  );
}
