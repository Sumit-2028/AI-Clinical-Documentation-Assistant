import { useState } from 'react'
import type { DocumentProvenanceEntry, PhysicianReviewFlag } from '../contracts/documents'
import { formatConfidence } from '../lib/confidence'
import { AlertIcon, ArrowIcon } from './icons'
import { SourceDocumentLink } from './SourceDocumentLink'

export function DocumentReviewFlags({ flags }: { flags: PhysicianReviewFlag[]; onProvenance?: (flag: PhysicianReviewFlag) => void }) {
  const [expandedFlag, setExpandedFlag] = useState<string | null>(null)

  return <div className="document-flag-list">{flags.length ? flags.map((flag) => {
    const flagKey = `${flag.type}-${flag.conflict_id ?? flag.description}`
    const expanded = expandedFlag === flagKey
    return <article className={`document-flag ${flag.risk_level === 'high' ? 'document-flag-high' : 'document-flag-review'}`} key={flagKey}>
      <div className="document-flag-icon"><AlertIcon /></div>
      <div className="document-flag-copy">
        <div><span className="flag-type">{flag.type === 'conflict' ? 'Conflicting information' : 'Review needed'}</span><span className="flag-risk">{flag.risk_level === 'high' ? 'High safety priority' : flag.risk_level ?? 'Review'}</span></div>
        <strong>{flag.description}</strong>
        <small>Physician review required · Related record: {flag.conflict_id ?? 'Not linked'}</small>
        <button className="document-provenance-link" aria-expanded={expanded} onClick={() => setExpandedFlag((current) => current === flagKey ? null : flagKey)}>{expanded ? 'Hide source information' : 'View source information'} <ArrowIcon /></button>
        {expanded && <ConflictSourceDetails entry={flag.source_provenance} />}
      </div>
    </article>
  }) : <p className="document-empty">No items require physician review.</p>}</div>
}

function ConflictSourceDetails({ entry }: { entry: DocumentProvenanceEntry }) {
  const sourcePosition = entry.source_text_span ? `${entry.source_text_span.start}–${entry.source_text_span.end}` : 'Not available'
  const verification = entry.trust_tier === 'current_encounter' ? 'Current encounter' : entry.trust_tier === 3 ? 'Unverified information' : entry.trust_tier === 2 ? 'Physician-approved' : 'Verified record'
  return <div className="document-source-details">
    <div className="document-source-details-heading"><span>Source document</span><SourceDocumentLink documentId={entry.source_document_id} className="document-source-file" label="Open attached record" /></div>
    <div className="document-source-details-grid"><div><span>Source</span><strong>{entry.source_document_id ?? 'Not linked'}</strong></div><div><span>Source position</span><strong>{sourcePosition}</strong></div><div><span>Input type</span><strong>{entry.input_modality}</strong></div><div><span>Language</span><strong>{(entry.source_language ?? 'unknown').toUpperCase()}</strong></div><div><span>Verification</span><strong>{verification}</strong></div><div><span>Confidence</span><strong>{formatConfidence(entry.extraction_confidence)}</strong></div></div>
    <div className="document-source-excerpt"><span>Relevant extracted clinical text</span><p>{entry.original_text}</p></div>
  </div>
}
