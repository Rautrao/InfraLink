import Link from 'next/link';

const links=[['/staff/dashboard','Dashboard'],['/staff/conflicts','Conflicts'],['/staff/permits','Permits'],['/staff/feedback','Feedback']];
export function StaffNav(){return <nav className="staff-nav" aria-label="Staff console navigation">{links.map(([href,label])=><Link key={href} href={href}>{label}</Link>)}</nav>}
