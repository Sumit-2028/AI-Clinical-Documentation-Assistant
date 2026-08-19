import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useStep1Output, useVerifyStep1Field } from '../hooks/useStep1'
import { AlertIcon, CheckIcon, XIcon } from '../components/icons'
import { ConfidenceBadge, RiskBadge } from '../components/Badges'
import { SectionCard } from '../components/SectionCard'
import { SourceDocumentLink } from '../components/SourceDocumentLink'
import type { ExtractedField } from '../contracts/step1Output'

interface VerificationNavigationState { fieldId?: string }
function requiresPhysicianReview(field: ExtractedField): boolean {
  if (field.review_status === 'approved' || field.review_status === 'rejected') return false
  return field.requires_doctor_review_before_memory_write || field.review_status === 'review_required' || field.review_status === 'pending'
}

export function VerificationPage() {
  const location = useLocation()
  const routeState = location.state as VerificationNavigationState | null
  const { data: output } = useStep1Output()
  const [selectedId, setSelectedId] = useState<string | null>(routeState?.fieldId ?? null)
  const reviewFields = output?.extracted_fields.filter(requiresPhysicianReview) ?? []
  const selected = reviewFields.find((field) => field.field_id === selectedId) ?? reviewFields[0]

  useEffect(() => {
    setSelectedId(routeState?.fieldId ?? null)
  }, [routeState?.fieldId])

  if (!output) return <div className="empty-loading">Loading verification record…</div>
  return <div className="page-stack"><div className="page-heading"><div><p className="eyebrow">PHYSICIAN REVIEW</p><h1>Review & correct extracted information</h1><p className="page-subtitle">Review uncertain information, correct the extracted value when needed, and confirm it against the original source.</p></div><div className="safety-pill"><AlertIcon /> Unverified information is blocked</div></div><div className="verification-grid"><SectionCard title="Source document" eyebrow="ORIGINAL INPUT" className="document-preview"><div className="document-toolbar"><SourceDocumentLink documentId={output.document_id} className="document-source-link" label="Open source record" /><span>Page 1 / 1</span></div><div className="document-sheet"><div className="document-stamp">MEDFLOW SCAN</div><p>{output.original_language_text ?? 'Original source text preserved for review.'}</p><p>Clinical information requiring physician review</p><div className="highlight-box">{selected?.raw_text ?? 'Select information to inspect'}</div></div><div className="document-caption">Original source preserved · {output.source_language.toUpperCase()} · {Math.round((output.translation_confidence ?? 0) * 100)}% translation confidence</div></SectionCard><SectionCard title="Extracted information" eyebrow={`${reviewFields.length} ITEMS · ${output.patient_id}`} className="field-review-card"><div className="field-review-list">{reviewFields.length > 0 ? reviewFields.map((field) => <FieldReviewItem key={field.field_id} field={field} selected={field.field_id === selected?.field_id} onSelect={() => setSelectedId(field.field_id)} />) : <div className="empty-loading">No items require physician review.</div>}</div>{selected && <VerificationActions key={selected.field_id} field={selected} />}</SectionCard></div><div className="safety-banner"><div className="safety-banner-icon"><AlertIcon /></div><div><strong>Unverified information cannot be added to the patient record.</strong><span>Only automatically cleared or physician-confirmed information can proceed.</span></div></div></div>
}

function FieldReviewItem({ field, selected, onSelect }: { field: ExtractedField; selected: boolean; onSelect: () => void }) {
  const currentValue = field.verified_text ?? field.standardized_text
  return <button className={`field-review-item ${selected ? 'selected' : ''}`} onClick={onSelect}><div className="field-review-heading"><span className="field-type">{field.field_type.replace(/_/g, ' ')}</span><RiskBadge highRisk={field.is_high_risk_field} /></div><div className="field-review-values"><span>{field.raw_text}</span><b>→</b><strong>{currentValue}</strong></div><div className="field-review-meta"><ConfidenceBadge field={field} /><span className="review-state">{field.review_status === 'approved' ? <><CheckIcon /> Approved</> : field.review_status === 'rejected' ? <><XIcon /> Rejected</> : <><AlertIcon /> Needs review</>}</span><span className="field-edit-hint">Edit value</span></div></button>
}

function VerificationActions({ field }: { field: ExtractedField }) {
  const [text, setText] = useState(field.verified_text ?? field.standardized_text)
  const [editing, setEditing] = useState(false)
  const [corrected, setCorrected] = useState(false)
  const verify = useVerifyStep1Field()
  const saveCorrection = () => { setCorrected(true); setEditing(false) }
  const cancelCorrection = () => { setText(field.verified_text ?? field.standardized_text); setEditing(false) }
  const submit = (approved: boolean) => verify.mutate({ field_id: field.field_id, verified_text: text, reviewer_id: 'phy_04', approved })
  return <div className="verification-actions"><div className="correction-source"><span>Original source</span><strong>{field.raw_text}</strong></div>{editing ? <label>Physician correction<input aria-label="Physician correction" value={text} onChange={(event) => setText(event.target.value)} /></label> : <div className="correction-current"><span>Current extracted value</span><strong>{text}</strong></div>}{!editing && !verify.isSuccess && <button className="secondary-button edit-value-button" onClick={() => setEditing(true)}>Edit value</button>}{editing && <div className="action-row"><button className="secondary-button" onClick={cancelCorrection}>Cancel</button><button className="confirm-button" onClick={saveCorrection} disabled={!text.trim()}><CheckIcon /> Save correction</button></div>}{corrected && <p className="success-copy"><CheckIcon /> Physician corrected</p>}<div className="action-row"><button className="reject-button" onClick={() => submit(false)} disabled={verify.isPending || verify.isSuccess}><XIcon /> Reject</button><button className="confirm-button" onClick={() => submit(true)} disabled={verify.isPending || verify.isSuccess || !text.trim()}><CheckIcon /> Confirm and allow</button></div>{verify.isSuccess && <p className="success-copy"><CheckIcon /> {verify.data.status === 'rejected' ? 'Review saved. Information remains excluded from the patient record.' : 'Review saved. Patient record access updated.'}</p>}</div>
}
