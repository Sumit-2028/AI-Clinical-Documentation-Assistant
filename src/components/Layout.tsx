import { NavLink, Outlet } from 'react-router-dom'
import { BellIcon, ClipboardIcon, GridIcon, HeartIcon, SearchIcon, UserIcon } from './icons'
import { useReviewQueue } from '../hooks/useStep1'

const navItems = [
  { label: 'Dashboard', path: '/', icon: GridIcon }, { label: 'Patients', path: '/patients', icon: UserIcon },
  { label: 'Review Queue', path: '/review-queue', icon: ClipboardIcon },
  { label: 'Upload & Process', path: '/upload', icon: UploadIconPlaceholder }, { label: 'Patient Memory', path: '/memory', icon: HeartIcon },
]

function UploadIconPlaceholder(props: React.SVGProps<SVGSVGElement>) { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}><path d="M12 16V4m0 0L8 8m4-4 4 4M5 14v5h14v-5" /></svg> }

export function Layout() {
  const { data: reviewQueue } = useReviewQueue()
  const reviewCount = reviewQueue?.reduce((total, output) => total + output.extracted_fields.filter((field) => field.requires_doctor_review_before_memory_write).length, 0) ?? 0
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="brand-mark"><HeartIcon /></div><div><div className="brand-name">MedFlow<span>AI</span></div><div className="brand-caption">Clinical intelligence</div></div></div><div className="workspace-label">WORKSPACE</div><nav>{navItems.map(({ label, path, icon: Icon }) => <NavLink key={path} to={path} end={path === '/'} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}><Icon /><span>{label}</span>{label === 'Review Queue' && reviewCount > 0 && <span className="nav-count">{reviewCount}</span>}</NavLink>)}</nav><div className="sidebar-footer"><div className="secure-line"><span className="secure-dot" /> Secure workspace</div><div className="profile"><div className="avatar">DR</div><div><strong>Dr. Riya Mehta</strong><span>Physician</span></div><span className="profile-more">•••</span></div></div></aside><main className="main-content"><header className="topbar"><div className="crumb"><span>MedFlow AI</span><b>/</b><span className="crumb-current">Clinical workspace</span></div><div className="top-actions"><button className="icon-button" aria-label="Search"><SearchIcon /></button><button className="icon-button notification" aria-label="Notifications"><BellIcon /><span /></button><div className="top-avatar">RM</div></div></header><div className="page-wrap"><Outlet /></div></main></div>
}
