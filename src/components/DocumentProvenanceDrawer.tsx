import type { DocumentProvenanceEntry } from '../contracts/documents'
import { formatConfidence } from '../lib/confidence'
import { CheckIcon, XIcon } from './icons'
import { SourceDocumentLink } from './SourceDocumentLink'

export function DocumentProvenanceDrawer({ entry, onClose }: { entry: DocumentProvenanceEntry; onClose: () => void }) {
  const tierLabel = entry.trust_tier === 3 ? 'Unverified information' : entry.trust_tier === 2 ? 'Physician-approved' : entry.trust_tier === 1 ? 'Verified record' : 'Current encounter'
  return <div className="drawer-backdrop" role="presentation" onClick={onClose}><aside className="provenance-drawer document-provenance-drawer" role="dialog" aria-label="Source and verification" onClick={(event) => event.stopPropagation()}>
    <div className="drawer-header"><div><p className="eyebrow">SOURCE & VERIFICATION</p><h2>Source information</h2></div><button className="icon-button" aria-label="Close source and verification" onClick={onClose}><XIcon /></button></div>
    <div className={`document-tier-detail ${entry.trust_tier === 3 ? 'document-tier-three' : ''}`}><span>{tierLabel}</span><strong>{entry.fact_id}</strong></div>
    <div className="drawer-section"><p className="drawer-label">Source document</p><SourceDocumentLink documentId={entry.source_document_id} className="drawer-document-link" /><div className="drawer-original"><p className="drawer-label">Original text</p><p>{entry.original_text}</p></div></div>
    <div className="drawer-section"><p className="drawer-label">Source details</p><div className="metadata-list"><div><span>Input type</span><strong>{entry.input_modality}</strong></div><div><span>Language</span><strong>{(entry.source_language ?? 'unknown').toUpperCase()}</strong></div><div><span>Extraction confidence</span><strong>{formatConfidence(entry.extraction_confidence)}</strong></div></div></div>
    <div className="drawer-footer"><CheckIcon /> Source and verification remain visible in the clinical draft</div>
  </aside></div>
}
