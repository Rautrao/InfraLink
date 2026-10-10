'use client';
import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { Button, Input, Select, Textarea, Card, toast, ErrorState, Skeleton } from '@/components/ui';
import maplibregl from 'maplibre-gl';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';

export default function NewWork() {
  const router = useRouter();
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const draw = useRef<any>(null);

  const [formData, setFormData] = useState({
    title: '', purpose: '', category: 'other', agency_id: '',
    road_name: '', planned_start: '', original_target_end: '',
    contractor_name: '', contractor_public: true, contact_name: '',
    contact_phone: '', contact_email: '', contact_channel: 'phone',
    disruption_type: 'none', disruption_note: '', is_public: true,
    geometry: null as any
  });

  const [conflicts, setConflicts] = useState<any[]>([]);
  const [showConflicts, setShowConflicts] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data: user, isLoading: userLoading, error: userError, refetch: refetchUser } = useQuery({ queryKey: ['auth-me'], queryFn: () => api<any>('/auth/me'), retry: false });
  const { data: agencies, isLoading: agenciesLoading, error: agenciesError, refetch: refetchAgencies } = useQuery({ queryKey: ['agencies'], queryFn: () => api<any[]>('/agencies') });
  const { data: config, isLoading: configLoading, error: configError, refetch: refetchConfig } = useQuery({ queryKey: ['config-public'], queryFn: () => api<any>('/config/public') });
  const referenceError = userError || agenciesError || configError;

  // Auto-fill agency if utility_editor
  useEffect(() => {
    if (user?.role === 'utility_editor' && user?.agency_id && !formData.agency_id) {
      setFormData(prev => ({ ...prev, agency_id: user.agency_id }));
    }
  }, [user, formData.agency_id]);

  useEffect(() => {
    if (!mapContainer.current || map.current) return;
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256 }
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm' }]
      },
      center: [73.8567, 18.5204], // Pune demo coords
      zoom: 12
    });

    draw.current = new MapboxDraw({
      displayControlsDefault: false,
      controls: { line_string: true, polygon: true, trash: true }
    });

    map.current.addControl(draw.current);

    const updateArea = () => {
      const data = draw.current.getAll();
      if (data.features.length > 0) {
        setFormData(prev => ({ ...prev, geometry: data.features[0].geometry }));
      } else {
        setFormData(prev => ({ ...prev, geometry: null }));
      }
    };

    map.current.on('draw.create', updateArea);
    map.current.on('draw.delete', updateArea);
    map.current.on('draw.update', updateArea);

    return () => { map.current?.remove(); };
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value
    }));
  };

  const handleInitialSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.geometry) return toast('Please draw a location on the map');
    setIsSubmitting(true);
    try {
      // Check for conflicts
      const checkRes = await api<any>('/geo/check', {
        method: 'POST',
        body: JSON.stringify({
          geometry: formData.geometry,
          planned_start: formData.planned_start,
          target_end: formData.original_target_end
        })
      });
      if (checkRes?.conflicts?.length > 0) {
        setConflicts(checkRes.conflicts);
        setShowConflicts(true);
        setIsSubmitting(false);
      } else {
        await submitWork();
      }
    } catch (err: any) {
      console.error(err);
      toast(err.message || 'Error checking conflicts. Submitting anyway...');
      await submitWork();
    }
  };

  const submitWork = async () => {
    setIsSubmitting(true);
    try {
      const res = await api<any>('/works', {
        method: 'POST',
        body: JSON.stringify({
          ...formData,
          current_target_end: formData.original_target_end
        })
      });
      toast('Work created successfully');
      router.push(`/staff/works/${res.id}`);
    } catch (err: any) {
      toast(err.message || 'Failed to create work');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto flex flex-col gap-6 pb-20">
      <h1 className="text-2xl font-bold">Submit New Work</h1>

      {(userLoading || agenciesLoading || configLoading) && <Skeleton className="skeleton-card"/>}
      {referenceError && <ErrorState onRetry={() => { void refetchUser(); void refetchAgencies(); void refetchConfig(); }} />}

      {showConflicts && (
        <Card className="p-6 border-orange-300 bg-orange-50 flex flex-col gap-4 shadow-sm">
          <h2 className="text-xl font-bold text-orange-800">⚠️ Possible Conflicts Detected</h2>
          <p className="text-sm text-orange-900">
            The spatial engine detected {conflicts.length} overlapping works during your planned dates.
            Please coordinate to minimize disruption.
          </p>
          <div className="max-h-64 overflow-y-auto bg-white border border-orange-200 rounded">
            <table className="w-full text-left text-sm">
              <thead className="bg-orange-100">
                <tr><th>Work Title</th><th>Overlap Days</th><th>Distance</th></tr>
              </thead>
              <tbody className="divide-y divide-orange-100">
                {conflicts.map((c, i) => (
                  <tr key={i} className="p-2">
                    <td className="p-2 font-medium">{c.work_b?.title || 'Unknown work'}</td>
                    <td className="p-2">{c.overlap_days} days</td>
                    <td className="p-2">{c.distance_m}m</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end gap-4 mt-2">
            <Button tone="secondary" onClick={() => setShowConflicts(false)}>Cancel & Adjust</Button>
            <Button tone="primary" onClick={submitWork} disabled={isSubmitting}>Submit Anyway</Button>
          </div>
        </Card>
      )}

      {!referenceError && !userLoading && !agenciesLoading && !configLoading && <form onSubmit={handleInitialSubmit} className="flex flex-col gap-6">
        <Card className="p-6 flex flex-col gap-4">
          <h2 className="text-lg font-semibold border-b pb-2">Basics</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium mb-1">Title</label>
              <Input name="title" value={formData.title} onChange={handleChange} required className="w-full" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium mb-1">Purpose (plain language)</label>
              <Textarea name="purpose" value={formData.purpose} onChange={handleChange} className="w-full" rows={2} />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Category</label>
              <Select name="category" value={formData.category} onChange={handleChange} required className="w-full">
                {config?.categories?.map((c: string) => <option key={c} value={c}>{c}</option>) || <option value="other">Other</option>}
              </Select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Agency</label>
              <Select name="agency_id" value={formData.agency_id} onChange={handleChange} required className="w-full" disabled={user?.role === 'utility_editor'}>
                <option value="">Select Agency</option>
                {agencies?.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
              </Select>
            </div>
          </div>
        </Card>

        <Card className="p-6 flex flex-col gap-4">
          <h2 className="text-lg font-semibold border-b pb-2">Location</h2>
          <div className="text-sm text-gray-600 mb-2">Draw a line or polygon on the map for this work segment.</div>
          <div ref={mapContainer} className="h-96 w-full rounded border bg-gray-100" />
          <div>
            <label className="block text-sm font-medium mb-1">Road/Area Name</label>
            <Input name="road_name" value={formData.road_name} onChange={handleChange} className="w-full" />
          </div>
        </Card>

        <Card className="p-6 flex flex-col gap-4">
          <h2 className="text-lg font-semibold border-b pb-2">Schedule & Impact</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Planned Start</label>
              <Input type="date" name="planned_start" value={formData.planned_start} onChange={handleChange} required className="w-full" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Target End</label>
              <Input type="date" name="original_target_end" value={formData.original_target_end} onChange={handleChange} required className="w-full" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Disruption Type</label>
              <Select name="disruption_type" value={formData.disruption_type} onChange={handleChange} className="w-full">
                <option value="none">None</option>
                <option value="restricted_access">Restricted Access</option>
                <option value="partial_closure">Partial Closure</option>
                <option value="full_closure">Full Closure</option>
              </Select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Disruption Note</label>
              <Input name="disruption_note" value={formData.disruption_note} onChange={handleChange} className="w-full" />
            </div>
          </div>
        </Card>

        <Card className="p-6 flex flex-col gap-4">
          <h2 className="text-lg font-semibold border-b pb-2">People</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Contractor Name</label>
              <Input name="contractor_name" value={formData.contractor_name} onChange={handleChange} className="w-full" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Contact Name (For public/internal queries)</label>
              <Input name="contact_name" value={formData.contact_name} onChange={handleChange} className="w-full" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Contact Phone</label>
              <Input name="contact_phone" value={formData.contact_phone} onChange={handleChange} className="w-full" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Contact Email</label>
              <Input type="email" name="contact_email" value={formData.contact_email} onChange={handleChange} className="w-full" />
            </div>
            <div className="col-span-2 flex gap-4 mt-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" name="contractor_public" checked={formData.contractor_public} onChange={handleChange} />
                Show contractor publicly
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" name="is_public" checked={formData.is_public} onChange={handleChange} />
                Make this entire work record public
              </label>
            </div>
          </div>
        </Card>

        <div className="flex justify-end gap-4">
          <Button type="button" tone="secondary" onClick={() => router.back()}>Cancel</Button>
          <Button type="submit" disabled={isSubmitting || showConflicts}>
            {isSubmitting ? 'Checking...' : 'Submit Work'}
          </Button>
        </div>
      </form>}
    </div>
  );
}
