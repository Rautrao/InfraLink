'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import Link from 'next/link';
import { Badge, Card, ErrorState, StatusChip, Skeleton, Timeline } from '@/components/ui';

export default function TicketDetail({ params }: { params: { ref_no: string } }) {
  const { data: ticket, isLoading, isError, refetch } = useQuery({
    queryKey: ['feedback', params.ref_no],
    queryFn: () => api<any>(`/feedback/${params.ref_no}`)
  });

  if (isLoading) return <div className="max-w-3xl mx-auto p-4"><Skeleton className="h-64" /></div>;
  if (isError || !ticket) return <div className="max-w-3xl mx-auto p-4"><ErrorState onRetry={() => refetch()} /></div>;

  const timelineItems = (ticket.events || []).map((e: any) => ({
    id: e.id,
    title: e.status ? `Status changed to ${e.status}` : 'Update',
    detail: e.message,
    date: e.at,
    by: e.responder_dept || 'System'
  }));

  // Add initial received event
  timelineItems.push({
    id: 'init',
    title: 'Received',
    detail: ticket.text,
    date: ticket.created_at,
    by: 'You'
  });

  // Sort descending
  timelineItems.sort((a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime());

  // Dummy SLA calculation
  const slaDate = new Date(ticket.created_at);
  slaDate.setDate(slaDate.getDate() + 3);

  return (
    <div className="max-w-3xl mx-auto p-4 flex flex-col gap-6 pb-20">
      <div className="flex flex-col gap-2 border-b pb-4">
        <div className="flex justify-between items-start">
          <div>
            <div className="font-mono font-bold text-blue-700 mb-1">{ticket.ref_no}</div>
            <h1 className="text-2xl font-bold capitalize">{ticket.kind}</h1>
          </div>
          <StatusChip status={ticket.status} />
        </div>
        <p className="text-gray-700 mt-2 p-4 bg-gray-50 rounded-lg whitespace-pre-wrap">{ticket.text}</p>
        {ticket.photo_url && (
          <img src={ticket.photo_url} alt="Attached evidence" className="mt-2 rounded max-w-sm border" />
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2">
          <Card className="p-6">
            <h2 className="text-lg font-bold mb-4">Resolution Timeline</h2>
            <Timeline items={timelineItems} />
          </Card>
        </div>
        <div className="flex flex-col gap-4">
          <Card className="p-4 bg-blue-50 border-blue-100">
            <h3 className="font-bold text-blue-900 mb-2">Service Level Info</h3>
            <p className="text-sm text-blue-800">
              Expected first response by: <br/>
              <strong>{slaDate.toLocaleDateString()}</strong>
            </p>
            {ticket.current_level > 1 && (
              <div className="mt-2 block">
                <Badge tone="warning">
                  Escalated to Level {ticket.current_level}
                </Badge>
              </div>
            )}
          </Card>

          {ticket.work_id && (
            <Card className="p-4">
              <h3 className="font-bold mb-2">Linked Project</h3>
              <Link href={`/works/${ticket.work_id}`} className="text-blue-600 hover:underline text-sm">
                View Project Details +'
              </Link>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
