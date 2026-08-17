import type { ReactNode } from 'react'
import { ActivityIcon, ArrowIcon, FileIcon, HeartIcon, UserIcon } from '../components/icons'
const iconMap = { patients: UserIcon, memory: HeartIcon, conflicts: ActivityIcon, documentation: FileIcon }
export function PlaceholderPage({ title, section }: { title: string; section: keyof typeof iconMap }) { const Icon = iconMap[section]; return <div className="placeholder-page"><div className="placeholder-icon"><Icon /></div><p className="eyebrow">COMING NEXT</p><h1>{title}</h1><p>This workspace is ready for the next stage of the clinical assistant experience.</p><button className="secondary-button">Return to dashboard <ArrowIcon /></button></div> }
export function ProcessingPage() { return <PlaceholderPage title="Processing jobs" section="documentation" /> }
