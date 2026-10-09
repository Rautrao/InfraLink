import './globals.css';
import { Providers } from './providers';
export const metadata = { title: 'Public Works Platform', description: 'Public works transparency and coordination' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body><Providers>{children}</Providers></body></html>; }
