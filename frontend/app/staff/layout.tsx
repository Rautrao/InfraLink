'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useRouter, usePathname } from 'next/navigation';
import { useEffect } from 'react';
import Link from 'next/link';

export default function StaffLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  
  const { data: user, isLoading, error } = useQuery({
    queryKey: ['auth-me'],
    queryFn: () => api<any>('/auth/me'),
    retry: false
  });

  useEffect(() => {
    if (!isLoading && (error || !user)) {
      if (pathname !== '/staff/login') {
        router.push('/staff/login');
      }
    }
  }, [isLoading, error, user, pathname, router]);

  if (isLoading) return <div className="p-8">Loading staff console...</div>;
  if (pathname === '/staff/login') return <>{children}</>;
  if (!user) return null;

  const role = user.role || 'staff';
  
  const navItems = [
    { label: 'Dashboard', path: '/staff/dashboard', roles: ['admin', 'commissioner', 'chief_engineer', 'superintending_engineer', 'executive_engineer', 'assistant_engineer', 'junior_engineer', 'utility_editor'] },
    { label: 'Works', path: '/staff/works', roles: ['admin', 'commissioner', 'chief_engineer', 'superintending_engineer', 'executive_engineer', 'assistant_engineer', 'junior_engineer', 'utility_editor', 'contractor', 'auditor'] },
    { label: 'Conflicts', path: '/staff/conflicts', roles: ['admin', 'commissioner', 'chief_engineer', 'superintending_engineer', 'executive_engineer', 'assistant_engineer', 'junior_engineer', 'utility_editor'] },
    { label: 'Permits', path: '/staff/permits', roles: ['admin', 'commissioner', 'chief_engineer', 'superintending_engineer', 'executive_engineer', 'assistant_engineer', 'junior_engineer', 'traffic_police'] },
    { label: 'Feedback', path: '/staff/feedback', roles: ['admin', 'commissioner', 'chief_engineer', 'superintending_engineer', 'executive_engineer', 'assistant_engineer', 'junior_engineer'] },
    { label: 'Import', path: '/staff/import', roles: ['admin', 'commissioner', 'utility_editor', 'junior_engineer', 'assistant_engineer', 'executive_engineer'] },
    { label: 'Audit', path: '/staff/audit', roles: ['admin', 'commissioner', 'auditor'] },
  ];

  const visibleNav = navItems.filter(item => item.roles.includes(role));

  return (
    <div className="flex h-screen bg-gray-50 flex-col">
      <header className="bg-blue-900 text-white p-4 flex justify-between items-center shadow-md">
        <div className="font-bold text-xl">Staff Console</div>
        <div className="flex items-center gap-4 text-sm">
          <span>{user.name} ({role}) {user.ward_id ? '- Ward Assigned' : ''}</span>
          <button onClick={() => { localStorage.removeItem('access_token'); router.push('/staff/login'); }} className="underline hover:text-blue-200">Logout</button>
        </div>
      </header>
      <div className="flex flex-1 overflow-hidden">
        <nav className="w-64 bg-white border-r shadow-sm flex flex-col p-4 gap-2 overflow-y-auto">
          {visibleNav.map(item => (
            <Link key={item.path} href={item.path} className={`p-2 rounded hover:bg-gray-100 ${pathname.startsWith(item.path) ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700'}`}>
              {item.label}
            </Link>
          ))}
          <Link href="/field" className="p-2 rounded hover:bg-gray-100 text-purple-700 font-medium mt-4 border border-purple-200">
            Field PWA 📱
          </Link>
        </nav>
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
      <style dangerouslySetInnerHTML={{__html: `
        /* Hide public header/footer if they render */
        .site-header, .site-footer { display: none !important; }
        #main-content { padding: 0 !important; max-width: none !important; margin: 0 !important; }
        body { margin: 0; padding: 0; height: 100vh; overflow: hidden; }
      `}} />
    </div>
  );
}
