'use client';
import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { Button, Input, Select, Textarea, Card, toast, Tabs, Badge, StatusChip, Timeline, Modal, LastUpdated } from '@/components/ui';

export default function WorkDetail({ params }: { params: { id: string } }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [statusModal, setStatusModal] = useState<{ open: boolean, toStatus: string }>({ open: false, toStatus: '' });
  const [statusForm, setStatusForm] = useState({ reason_code: '', explanation: '' });
  
  const [dateModal, setDateModal] = useState(false);
  const [dateForm, setDateForm] = useState({ new_target_end: '', reason_code: '', explanation: '' });

  const [updateForm, setUpdateForm] = useState({ text: '', pct_complete: 0, is_public: true });

  const { data: work, refetch } = useQuery({ queryKey: ['work', params.id], queryFn: () => api<any>(`/works/${params.id}`) });
  const { data: history } = useQuery({ queryKey: ['work-history', params.id], queryFn: () => api<any[]>(`/works/${params.id}/history`) });
  const { data: config } = useQuery({ queryKey: ['config-public'], queryFn: () => api<any>('/config/public') });

  if (!work) return <div className="p-12 text-center text-gray-500">Loading work details...</div>;

  const validTransitions: Record<string, string[]> = {
    planned: ['permitted', 'paused'],
    permitted: ['ongoing', 'paused'],
    ongoing: ['completed', 'paused'],
    paused: ['ongoing', 'completed'],
    completed: ['restoration_verified'],
    restoration_verified: ['closed']
  };

  const nextStatuses = validTransitions[work.status] || [];

  const handleStatusChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (['paused'].includes(statusModal.toStatus) && statusForm.explanation.length < 15) {
      return toast('Explanation must be at least 15 characters.');
    }
    try {
      await api(`/works/${params.id}/status`, {
        method: 'POST',
        body: JSON.stringify({
          to_status: statusModal.toStatus,
          reason_code: statusForm.reason_code || undefined,
          explanation: statusForm.explanation || undefined
        })
      });
      toast(`Status updated to ${statusModal.toStatus}`);
      setStatusModal({ open: false, toStatus: '' });
      refetch();
    } catch (err: any) {
      toast(err.message || 'Failed to update status');
    }
  };

  const handleReviseDate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api(`/works/${params.id}/dates`, {
        method: 'POST',
        body: JSON.stringify(dateForm)
      });
      toast('Date revised successfully');
      setDateModal(false);
      refetch();
    } catch (err: any) {
      toast(err.message || 'Failed to revise date');
    }
  };

  const handlePostUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api(`/works/${params.id}/updates`, {
        method: 'POST',
        body: JSON.stringify(updateForm)
      });
      toast('Update posted');
      setUpdateForm({ text: '', pct_complete: work.pct_complete, is_public: true });
      refetch();
    } catch (err: any) {
      toast(err.message || 'Failed to post update');
    }
  };

  return (
    <div className="max-w-6xl mx-auto flex flex-col gap-6 pb-20">
      <div className="flex justify-between items-start">
        <div>
          <div className="text-sm font-mono text-blue-600">{work.ref_no}</div>
          <h1 className="text-3xl font-bold text-gray-900">{work.title}</h1>
          <div className="flex gap-2 mt-2 items-center">
            <StatusChip status={work.status} />
            <Badge>{work.category.replace('_', ' ')}</Badge>
            {work.delayed && <Badge tone="critical">Delayed</Badge>}
            <LastUpdated value={work.last_update_at} className="text-gray-500 text-sm ml-4" />
          </div>
        </div>
        <div className="flex gap-2">
          {nextStatuses.map(s => (
            <Button key={s} tone="primary" onClick={() => setStatusModal({ open: true, toStatus: s })}>
              Mark as {s.replace('_', ' ')}
            </Button>
          ))}
        </div>
      </div>

      <Tabs 
        value={activeTab} 
        onChange={setActiveTab}
        items={[
          { id: 'overview', label: 'Overview' },
          { id: 'updates', label: 'Updates' },
          { id: 'dates', label: 'Dates' },
          { id: 'history', label: 'History' },
          { id: 'evidence', label: 'Evidence' }
        ]}
      />

      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="col-span-2 p-6 flex flex-col gap-4">
            <h2 className="text-lg font-bold">Details</h2>
            <p>{work.purpose || 'No purpose provided.'}</p>
            <div className="grid grid-cols-2 gap-4 mt-4">
              <div>
                <div className="text-sm text-gray-500">Agency</div>
                <div className="font-medium">{work.agency?.name}</div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Location</div>
                <div className="font-medium">{work.road_name || 'N/A'} ({work.ward?.name})</div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Contractor</div>
                <div className="font-medium">{work.contractor_name || 'N/A'}</div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Contact</div>
                <div className="font-medium">{work.contact?.name || 'N/A'} - {work.contact?.phone_masked}</div>
              </div>
            </div>
          </Card>
          <div className="flex flex-col gap-6">
            <Card className="p-6 flex flex-col gap-2">
              <h2 className="text-lg font-bold">Schedule</h2>
              <div className="flex justify-between border-b pb-2">
                <span className="text-gray-600">Start</span>
                <span className="font-medium">{work.planned_start}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="text-gray-600">Target</span>
                <span className="font-medium">{work.current_target_end}</span>
              </div>
              <div className="mt-2 text-center text-sm font-medium">
                {work.pct_complete}% Complete
              </div>
              <div className="w-full bg-gray-200 h-2 rounded mt-1">
                <div className="bg-blue-600 h-2 rounded" style={{ width: `${work.pct_complete}%` }} />
              </div>
            </Card>
            <Card className="p-6 flex flex-col gap-2">
              <h2 className="text-lg font-bold">Impact</h2>
              <div className="font-medium text-orange-700">{work.disruption?.type.replace('_', ' ')}</div>
              <p className="text-sm">{work.disruption?.note || 'No notes'}</p>
            </Card>
          </div>
        </div>
      )}

      {activeTab === 'updates' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="col-span-2 flex flex-col gap-4">
            <h2 className="text-lg font-bold">Progress Updates</h2>
            {work.updates?.length ? work.updates.map((u: any) => (
              <Card key={u.id} className="p-4">
                <div className="flex justify-between text-sm text-gray-500 mb-2">
                  <span>{new Date(u.at).toLocaleString()}</span>
                  <span>{u.pct_complete}%</span>
                </div>
                <p>{u.text}</p>
                {!u.is_public && <Badge tone="neutral">Internal Only</Badge>}
              </Card>
            )) : <div className="text-gray-500">No updates yet.</div>}
          </div>
          <Card className="p-6">
            <h2 className="text-lg font-bold mb-4">Post Update</h2>
            <form onSubmit={handlePostUpdate} className="flex flex-col gap-4">
              <Textarea 
                placeholder="What progress was made today?" 
                value={updateForm.text} 
                onChange={e => setUpdateForm({ ...updateForm, text: e.target.value })}
                required 
                rows={4}
              />
              <div>
                <label className="block text-sm mb-1">New Completion %</label>
                <Input 
                  type="number" min="0" max="100" 
                  value={updateForm.pct_complete} 
                  onChange={e => setUpdateForm({ ...updateForm, pct_complete: parseInt(e.target.value) || 0 })}
                  required 
                />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input 
                  type="checkbox" 
                  checked={updateForm.is_public} 
                  onChange={e => setUpdateForm({ ...updateForm, is_public: e.target.checked })}
                />
                Public Update
              </label>
              <Button type="submit">Post Update</Button>
            </form>
          </Card>
        </div>
      )}

      {activeTab === 'dates' && (
        <Card className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-lg font-bold">Date Revisions</h2>
            <Button onClick={() => setDateModal(true)}>Revise Target Date</Button>
          </div>
          <table className="w-full text-left border-collapse">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="p-3">Date Revised</th>
                <th className="p-3">Old Target</th>
                <th className="p-3">New Target</th>
                <th className="p-3">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {work.date_revisions?.map((r: any) => (
                <tr key={r.id}>
                  <td className="p-3 text-sm">{new Date(r.at).toLocaleDateString()}</td>
                  <td className="p-3">{r.old}</td>
                  <td className="p-3 font-medium">{r.new}</td>
                  <td className="p-3 text-sm">
                    <strong>{r.reason_code}</strong><br/>
                    <span className="text-gray-500">{r.explanation}</span>
                  </td>
                </tr>
              ))}
              {!work.date_revisions?.length && <tr><td colSpan={4} className="p-4 text-center text-gray-500">No date revisions.</td></tr>}
            </tbody>
          </table>
        </Card>
      )}

      {activeTab === 'history' && (
        <Card className="p-6">
          <h2 className="text-lg font-bold mb-6">Full Timeline</h2>
          {history ? <Timeline items={history.map((h: any) => ({
            title: h.type,
            detail: h.description,
            date: h.at,
            by: h.by_user_name
          }))} /> : <div className="text-gray-500">Loading history...</div>}
        </Card>
      )}

      {activeTab === 'evidence' && (
        <Card className="p-6">
          <h2 className="text-lg font-bold mb-4">Evidence & Photos</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {work.evidence?.length ? work.evidence.map((e: any) => (
              <div key={e.id} className="border rounded overflow-hidden shadow-sm">
                <img src={e.public_url} alt={e.kind} className="w-full h-32 object-cover bg-gray-100" />
                <div className="p-2 text-xs">
                  <Badge>{e.kind}</Badge>
                  <div className="mt-1 text-gray-500">{new Date(e.taken_at).toLocaleDateString()}</div>
                </div>
              </div>
            )) : <div className="col-span-4 p-8 text-center text-gray-500">No evidence uploaded yet.</div>}
          </div>
        </Card>
      )}

      {/* Status Modal */}
      <Modal open={statusModal.open} title={`Change status to ${statusModal.toStatus.replace('_', ' ')}`} onClose={() => setStatusModal({ open: false, toStatus: '' })}>
        <form onSubmit={handleStatusChange} className="p-4 flex flex-col gap-4">
          <p className="text-sm text-gray-600">Please provide a reason for this status change if it involves a delay or pause.</p>
          <div>
            <label className="block text-sm mb-1">Reason Code (Optional unless pausing)</label>
            <Select value={statusForm.reason_code} onChange={e => setStatusForm({ ...statusForm, reason_code: e.target.value })} className="w-full">
              <option value="">Select Reason</option>
              {config?.reason_codes?.map((c: string) => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
            </Select>
          </div>
          <div>
            <label className="block text-sm mb-1">Explanation (Required if paused)</label>
            <Textarea value={statusForm.explanation} onChange={e => setStatusForm({ ...statusForm, explanation: e.target.value })} className="w-full" rows={3} />
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <Button tone="secondary" type="button" onClick={() => setStatusModal({ open: false, toStatus: '' })}>Cancel</Button>
            <Button type="submit">Confirm Change</Button>
          </div>
        </form>
      </Modal>

      {/* Revise Date Modal */}
      <Modal open={dateModal} title="Revise Target Date" onClose={() => setDateModal(false)}>
        <form onSubmit={handleReviseDate} className="p-4 flex flex-col gap-4">
          <div>
            <label className="block text-sm mb-1">New Target End Date</label>
            <Input type="date" value={dateForm.new_target_end} onChange={e => setDateForm({ ...dateForm, new_target_end: e.target.value })} required className="w-full" />
          </div>
          <div>
            <label className="block text-sm mb-1">Reason Code</label>
            <Select value={dateForm.reason_code} onChange={e => setDateForm({ ...dateForm, reason_code: e.target.value })} required className="w-full">
              <option value="">Select Reason</option>
              {config?.reason_codes?.map((c: string) => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
            </Select>
          </div>
          <div>
            <label className="block text-sm mb-1">Explanation</label>
            <Textarea value={dateForm.explanation} onChange={e => setDateForm({ ...dateForm, explanation: e.target.value })} required className="w-full" rows={3} />
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <Button tone="secondary" type="button" onClick={() => setDateModal(false)}>Cancel</Button>
            <Button type="submit">Revise Date</Button>
          </div>
        </form>
      </Modal>

    </div>
  );
}
