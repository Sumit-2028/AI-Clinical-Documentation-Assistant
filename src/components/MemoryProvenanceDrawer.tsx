import type { MemoryFact } from '../contracts/memory'
import { CheckIcon, XIcon } from './icons'
import { formatConfidence } from '../lib/confidence'
import { SourceDocumentLink } from './SourceDocumentLink'

export function MemoryProvenanceDrawer({ fact, onClose }: { fact: MemoryFact; onClose: () => void }) {
  return <div className="drawer-backdrop" role="presentation" onClick={onClose}><aside className="provenance-drawer" role="dialog" aria-label="Source and verification" onClick={(click) => click.stopPropagation()}>
    <div className="drawer-header"><div><p className="eyebrow">SOURCE & VERIFICATION</p><h2>Patient record details</h2></div><button className="icon-button" aria-label="Close source and verification" onClick={onClose}><XIcon /></button></div>
    <div className="drawer-event"><span className={`entity-pill entity-${fact.entity_type.toLowerCase()}`}>{fact.entity_type}</span><strong>{fact.normalized_concept}</strong><span>{fact.event_id}</span></div>
    <div className="drawer-section"><p className="drawer-label">Source document</p><SourceDocumentLink documentId={fact.source_document_id} className="drawer-document-link" /><div className="span-box memory-span"><div><span>Start</span><strong>{fact.source_text_span.start}</strong></div><div><span>End</span><strong>{fact.source_text_span.end}</strong></div><div><span>Clinical record group</span><strong>{fact.concept_thread_id}</strong></div></div></div>
    <div className="drawer-section"><p className="drawer-label">Source information</p><div className="metadata-list"><div><span>Input type</span><strong>{fact.input_modality}</strong></div><div><span>Language</span><strong>{fact.source_language.toUpperCase()}</strong></div><div><span>Translation confidence</span><strong className="verified-text">{fact.translation_confidence === null ? 'Not applicable' : formatConfidence(fact.translation_confidence)}</strong></div></div></div>
    <div className="drawer-section"><p className="drawer-label">Clinical interpretation</p><div className="metadata-list"><div><span>Extraction confidence</span><strong>{formatConfidence(fact.extraction_confidence)}</strong></div><div><span>Clinical interpretation confidence</span><strong>{formatConfidence(fact.contextualization_confidence)}</strong></div><div><span>Concept match confidence</span><strong>{fact.thread_match_confidence}</strong></div></div></div>
    <div className="drawer-section"><p className="drawer-label">Verification</p><div className="metadata-list"><div><span>Verification level</span><strong>{fact.trust_tier === 3 ? 'Unverified information' : fact.trust_tier === 2 ? 'Physician-approved' : 'Verified record'}</strong></div><div><span>Review status</span><strong>{fact.reviewed_status.replace(/_/g, ' ')}</strong></div><div><span>Clinical date</span><strong>{new Date(fact.event_timestamp).toLocaleDateString('en-IN')}</strong></div><div><span>Recorded at</span><strong>{new Date(fact.ingestion_timestamp).toLocaleString('en-IN')}</strong></div></div></div>
    <div className="drawer-footer"><CheckIcon /> Historical information remains visible and unchanged</div>
  </aside></div>
}
