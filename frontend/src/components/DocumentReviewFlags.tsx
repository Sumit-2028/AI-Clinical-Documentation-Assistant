import type { PhysicianReviewFlag } from '../contracts/documents'
import { AlertIcon, ArrowIcon } from './icons'

export function DocumentReviewFlags({ flags, onProvenance }: { flags: PhysicianReviewFlag[]; onProvenance: (flag: PhysicianReviewFlag) => void }) {
  return <div className="document-flag-list">{flags.length ? flags.map((flag) => <article className={`document-flag ${flag.risk_level === 'high' ? 'document-flag-high' : 'document-flag-review'}`} key={`${flag.type}-${flag.conflict_id ?? flag.description}`}><div className="document-flag-icon"><AlertIcon /></div><div className="document-flag-copy"><div><span className="flag-type">{flag.type === 'conflict' ? 'Conflicting information' : 'Review needed'}</span><span className="flag-risk">{flag.risk_level === 'high' ? 'High safety priority' : flag.risk_level ?? 'Review'}</span></div><strong>{flag.description}</strong><small>Related record: {flag.conflict_id ?? 'Not linked'}</small><button className="document-provenance-link" onClick={() => onProvenance(flag)}>View source information <ArrowIcon /></button></div></article>) : <p className="document-empty">No items require physician review.</p>}</div>
}
