'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Button } from '@/components/ui';
import { useT } from '@/lib/i18n';
import { usePreferences } from '@/lib/preferences';
import { Bell } from 'lucide-react';
import { useEffect, useState } from 'react';

type Resident = { name?: string; phone?: string };

const links = [
  { href: '/works?view=map', key: 'map' as const }, { href: '/works?view=list', key: 'list' as const },
  { href: '/dashboard', key: 'dashboard' as const }, { href: '/open-data', key: 'openData' as const }, { href: '/me/follows', key: 'follows' as const },
];
export function SiteHeader() {
  const pathname=usePathname(); const {t,language,setLanguage}=useT(); const {lowBandwidth,toggleLowBandwidth}=usePreferences();
  const [resident, setResident] = useState<Resident | null>(null);
  useEffect(() => {
    const readResident = () => {
      try {
        const stored = localStorage.getItem('resident_user');
        setResident(stored ? JSON.parse(stored) as Resident : null);
      } catch { setResident(null); }
    };
    readResident();
    window.addEventListener('resident-auth-changed', readResident);
    window.addEventListener('storage', readResident);
    return () => {
      window.removeEventListener('resident-auth-changed', readResident);
      window.removeEventListener('storage', readResident);
    };
  }, []);
  if (pathname === '/field') return null;
  return <header className="site-header"><div className="header-inner"><Link href="/" className="brand"><span className="brand-mark" aria-hidden="true">PW</span>{t('brand')}</Link><nav className="main-nav" aria-label={t('mainNavigation')}>{links.map(link=><Link key={link.href} href={link.href} aria-current={pathname===link.href.split('?')[0]?'page':undefined}>{t(link.key)}</Link>)}<Link href="/me/feedback" aria-current={pathname==='/me/feedback'?'page':undefined}>{t('myFeedback')}</Link></nav><div className="header-tools"><Link href="/me/follows" title={t('notifications')} aria-label={t('notifications')} className="ui-button ui-button-quiet"><Bell aria-hidden="true" size={19}/></Link><Button tone="secondary" onClick={toggleLowBandwidth} aria-pressed={lowBandwidth} title={t('lowBandwidth')}>{lowBandwidth?'◉':'◌'} <span className="desktop-only">{lowBandwidth?t('lowBandwidthOn'):t('lowBandwidth')}</span></Button><Button tone="quiet" onClick={()=>setLanguage(language==='en'?'hi':'en')} aria-label={language==='en'?t('switchToHindi'):t('switchToEnglish')}>{t('language')}</Button>{resident?<Link href="/me/follows" className="resident-name" title={resident.phone || resident.name}>{resident.name || resident.phone || t('login')}</Link>:<Link href="/login" className="ui-button ui-button-primary">{t('login')}</Link>}</div></div></header>;
}
export function SiteFooter(){const pathname=usePathname();const {t}=useT();if (pathname === '/field') return null;return <footer className="site-footer"><div className="footer-inner"><div><h2>{t('brand')}</h2><p>{t('about')} · Demo City</p><p>{t('linkedNotReplaced')}</p></div><div><h2>{t('grievances')}</h2><div className="link-row"><a href="https://aaplesarkar.mahaonline.gov.in/" target="_blank" rel="noreferrer">CM helpline ↗</a><a href="https://pgportal.gov.in/" target="_blank" rel="noreferrer">CPGRAMS ↗</a><a href="https://rtionline.gov.in/" target="_blank" rel="noreferrer">RTI ↗</a><Link href="/field">⚡ {t('fieldPwa')} ↗</Link></div></div><div><Link href="/open-data">{t('openData')}</Link><p>© 2026 Public Works Tracker</p></div></div></footer>}

