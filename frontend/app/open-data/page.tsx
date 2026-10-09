'use client';
import { Card, Button } from '@/components/ui';
import Link from 'next/link';

export default function OpenDataPage() {
  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">Open Data API & Downloads</h1>
      <p className="text-lg text-gray-600">Access public infrastructure data through our API or download static files.</p>
      
      <Card className="p-6">
        <h2 className="text-xl font-bold mb-2">Static Downloads</h2>
        <div className="flex gap-4 mt-4">
          <Link href="/api/v1/public_api/works.csv" download>
            <Button tone="secondary">Download CSV</Button>
          </Link>
          <Link href="/api/v1/public_api/works.geojson" download>
            <Button tone="secondary">Download GeoJSON</Button>
          </Link>
        </div>
      </Card>
      
      <Card className="p-6">
        <h2 className="text-xl font-bold mb-2">REST API Endpoints</h2>
        <ul className="list-disc pl-5 space-y-2 mt-4 text-gray-700">
          <li><strong>GET /api/v1/works</strong> - List public works.</li>
          <li><strong>GET /api/v1/works/geojson</strong> - Spatial works.</li>
          <li><strong>GET /api/v1/reports/summary</strong> - Dashboard KPI data.</li>
        </ul>
      </Card>
    </div>
  );
}
