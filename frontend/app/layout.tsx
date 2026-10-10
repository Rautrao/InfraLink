import './globals.css';
import { Providers } from './providers';
import { SiteFooter, SiteHeader } from '@/components/SiteShell';
import 'maplibre-gl/dist/maplibre-gl.css';
export const metadata = { title: 'Public Works Tracker | Demo City', description: 'Find public works, schedules and road disruptions in Demo City.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body><Providers>{process.env.NEXT_PUBLIC_DEV === 'true' && <div className="demo-mode-banner" role="status">Demo mode</div>}<a className="skip-link" href="#main-content">Skip to content</a><SiteHeader/><div id="main-content">{children}</div><SiteFooter/></Providers></body></html>; }
