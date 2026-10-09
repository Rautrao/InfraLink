'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import Link from 'next/link';
import { Badge, Button, Card, EmptyState, ErrorState, StatusChip, Skeleton, LastUpdated } from '@/components/ui';

export default function MyFeedback() {
  const { data: tickets, isLoading, isError, refetch } = useQuery({
    queryKey: ['my-feedback'],
    queryFn: () => api<any[]>('/me/feedback')
  });

  if (isLoading) return <div className="max-w-4xl mx-auto p-4"><Skeleton className="h-32 mb-4" /><Skeleton className="h-32 mb-4" /></div>;
  if (isError) return <div className="max-w-4xl mx-auto p-4"><ErrorState onRetry={() => refetch()} /></div>;
  
  if (!tickets || tickets.length === 0) {
    return (
      <div className="max-w-4xl mx-auto p-4">
        <h1 className="text-2xl font-bold mb-4">My Feedback & Reports</h1>
        <EmptyState title="No feedback submitted" detail="You haven't submitted any questions or reports yet." />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-4 flex flex-col gap-6 pb-20">
      <h1 className="text-2xl font-bold">My Feedback & Reports</h1>
      
      <div className="flex flex-col gap-4">
        {tickets.map((ticket: any) => (
          <Card key={ticket.id} className="p-4 flex flex-col md:flex-row justify-between md:items-start gap-4 hover:shadow-md transition-shadow">
            <div className="flex flex-col gap-2 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm text-blue-600 font-bold">{ticket.ref_no}</span>
                <StatusChip status={ticket.status} />
                <Badge>{ticket.kind}</Badge>
                {ticket.current_level > 1 && (
                  <Badge tone="warning">Escalated to L{ticket.current_level}</Badge>
                )}
              </div>
              
              <div className="text-gray-800 line-clamp-2 mt-1">
                "{ticket.text}"
              </div>
              
              <div className="text-sm text-gray-500 mt-2 flex flex-col gap-1">
                {ticket.work_id ? (
                  <Link href={`/works/${ticket.work_id}`} className="hover:underline hover:text-blue-600">
                    Linked to Project View
                  </Link>
                ) : (
                  <span>General Feedback</span>
                )}
                <LastUpdated value={ticket.last_response_at || ticket.created_at} />
              </div>
            </div>
            
            <div className="flex flex-col md:items-end gap-2 shrink-0">
              <Link href={`/feedback/${ticket.ref_no}`}>
                <Button tone="secondary">View Details</Button>
              </Link>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
