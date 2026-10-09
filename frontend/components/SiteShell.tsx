'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Button } from '@/components/ui';
import { useT } from '@/lib/i18n';
import { usePreferences } from '@/lib/preferences';

const links = [
  { href: '/works?view=map', key: 'map' as const }, { href: '/works?view=list', key: 'list' as const },
  { href: '/dashboard', key: 'dashboard' as const }, { href: '/open-data', key: 'openData' as const }, { href: '/follows', key: 'follows' as const },
];
export function SiteHeader() {
  const pathname=usePathname(); const {t,language,setLanguage}=useT(); const {lowBandwidth,toggleLowBandwidth}=usePreferences();
  return <header className="site-header"><div className="header-inner"><Link href="/" className="brand"><span className="brand-mark" aria-hidden="true">⌖</span>{t('brand')}</Link><nav className="main-nav" aria-label="Main navigation">{links.map(link=><Link key={link.href} href={link.href} aria-current={pathname===link.href.split('?')[0]?'page':undefined}>{t(link.key)}</Link>)}</nav><div className="header-tools"><Button tone="secondary" onClick={toggleLowBandwidth} aria-pressed={lowBandwidth} title={t('lowBandwidth')}>{lowBandwidth?'◉':'◌'} <span className="desktop-only">{lowBandwidth?t('lowBandwidthOn'):t('lowBandwidth')}</span></Button><Button tone="quiet" onClick={()=>setLanguage(language==='en'?'hi':'en')} aria-label={language==='en'?'Switch to Hindi':'Switch to English'}>{t('language')}</Button><Link href="/login" className="ui-button ui-button-primary">{t('login')}</Link></div></div></header>;
}
export function SiteFooter(){const {t}=useT();return <footer className="site-footer"><div className="footer-inner"><div><h2>{t('brand')}</h2><p>{t('about')} · Demo City</p><p>{t('linkedNotReplaced')}</p></div><div><h2>{t('grievances')}</h2><div className="link-row"><a href="https://aaplesarkar.mahaonline.gov.in/" target="_blank" rel="noreferrer">CM helpline ↗</a><a href="https://pgportal.gov.in/" target="_blank" rel="noreferrer">CPGRAMS ↗</a><a href="https://rtionline.gov.in/" target="_blank" rel="noreferrer">RTI ↗</a></div></div><div><a href="/open-data">{t('openData')}</a><p>© 2026 Public Works Tracker</p></div></div></footer>}
