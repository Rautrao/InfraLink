'use client';
import { Card, Button } from '@/components/ui';
import { useT } from '@/lib/i18n';

const apiBase=process.env.NEXT_PUBLIC_API_BASE??'http://localhost:4000/api/v1';
export default function OpenDataPage() {
  const {t}=useT();
  return <main className="page-wrap space-y-6"><h1 className="page-title">{t('openApiTitle')}</h1><p className="page-lede">{t('openApiDescription')}</p><Card className="p-6"><h2 className="text-xl font-bold mb-2">{t('staticDownloads')}</h2><div className="flex gap-4 mt-4"><a href={`${apiBase}/open/works.csv`}><Button tone="secondary">{t('downloadCsv')}</Button></a><a href={`${apiBase}/open/works.geojson`}><Button tone="secondary">{t('downloadGeo')}</Button></a></div></Card><Card className="p-6"><h2 className="text-xl font-bold mb-2">{t('apiEndpoints')}</h2><ul className="list-disc pl-5 space-y-2 mt-4 text-gray-700"><li><strong>GET /api/v1/works</strong> — {t('publicWorksEndpoint')}</li><li><strong>GET /api/v1/works/geojson</strong> — {t('spatialWorksEndpoint')}</li><li><strong>GET /api/v1/reports/summary</strong> — {t('dashboardEndpoint')}</li></ul></Card></main>;
}
