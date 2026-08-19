import type { ClinicalEvent } from '../contracts/clinicalEvent'
import { AlertIcon, ArrowIcon, CheckIcon, FileIcon, XIcon } from './icons'
import { formatConfidence } from '../lib/confidence'

export type ClinicalFindingResolution = 'added' | 'accepted' | 'rejected'

interface ClinicalEventCardProps {
  event: ClinicalEvent
  onProvenance: (event: ClinicalEvent) => void
  onApprove?: (event: ClinicalEvent) => void
  onReject?: (event: ClinicalEvent) => void
  onUseSuggestion?: (event: ClinicalEvent) => void
  onEditInterpretation?: (event: ClinicalEvent) => void
  interpretation?: string
  interpretationResolution?: 'confirmed' | 'corrected'
  resolution?: ClinicalFindingResolution
  actionPending?: boolean
}

export function ClinicalEventCard({ event, onProvenance, onApprove, onReject, onUseSuggestion, onEditInterpretation, interpretation, interpretationResolution, resolution, actionPending = false }: ClinicalEventCardProps) {
  const isSafetyEligible = event.validation_status === 'valid'
  const isAccepted = resolution === 'accepted'
  const isBlocked = !isSafetyEligible && !isAccepted
  const hasMedicationAttributes = Object.values(event.medication_attributes).some((value) => value !== null)
  const hasLabAttributes = Object.values(event.lab_attributes).some((value) => value !== null)
  const needsInterpretationReview = !resolution && ((event.ambiguous_abbreviation_resolved.was_ambiguous && !interpretationResolution) || event.gemini_contextualization_confidence < 0.8 || !isSafetyEligible)
  const needsPhysicianReview = needsInterpretationReview
  const processedText = interpretation ?? event.processed_text
  const frequency = interpretation ?? event.medication_attributes.frequency

  return <article className={`clinical-event-card ${isBlocked ? 'blocked-event' : ''} ${isAccepted ? 'accepted-event' : ''}`}>
    <div className="event-card-header">
      <div className="event-title"><span className={`entity-icon entity-${event.entity_type.toLowerCase()}`}>{event.entity_type.slice(0, 1)}</span><div><div className="event-kicker"><span>{displayEntityType(event.entity_type)}</span><span className="event-local-id">{event.event_local_id}</span></div><h3>{event.normalized_concept}</h3></div></div>
      <div className={`validation-state ${isAccepted ? 'valid' : isSafetyEligible ? needsPhysicianReview ? 'review' : 'valid' : 'invalid'}`}>{isAccepted ? <><CheckIcon /> Accepted</> : needsPhysicianReview ? <><AlertIcon /> Review required</> : <><CheckIcon /> Safe to review</>}</div>
    </div>
    <div className="event-text-row"><div><span className="event-label">Original text</span><p>{event.original_text}</p></div><ArrowIcon /><div><span className="event-label">Processed text</span><p className="processed-value">{processedText}</p></div></div>
    <div className="event-detail-grid"><Detail label="Standardized clinical concept" value={event.snomed_ct_id ?? 'Not mapped'} mono /><Detail label="Clinical area" value={event.clinical_domain} /><Detail label="Clinical finding" value={event.assertion} tone={event.assertion === 'negated' ? 'negative' : undefined} /></div>
    <div className="confidence-row"><AbbreviationSummary event={event} interpretation={interpretation} interpretationResolution={interpretationResolution} needsReview={needsInterpretationReview} onUseSuggestion={onUseSuggestion} onEditInterpretation={onEditInterpretation} actionPending={actionPending} /></div>
    {event.relationships.length > 0 && <div className="event-subsection"><span className="event-label">Related findings</span><div className="relationship-list">{event.relationships.map((relationship) => <span key={`${relationship.relation_type}-${relationship.target_event_local_id}`}><strong>{relationship.relation_type.replace(/_/g, ' ')}</strong><ArrowIcon />{relationship.target_event_local_id}</span>)}</div></div>}
    {hasMedicationAttributes && <AttributeSection title="Medication details" items={[["Dose", event.medication_attributes.dosage], ["Strength", event.medication_attributes.strength], ["Frequency", frequency], ["Route", event.medication_attributes.route]]} />}
    {hasLabAttributes && <AttributeSection title="Laboratory details" items={[["Test", event.lab_attributes.test_name], ["Value", event.lab_attributes.value], ["Unit", event.lab_attributes.unit]]} />}
    <div className="event-card-footer"><span><FileIcon /> Source information · positions {event.source_text_span.start}-{event.source_text_span.end}</span><div className="event-card-actions"><button className="provenance-button" onClick={() => onProvenance(event)} disabled={actionPending}>View source information <ArrowIcon /></button>{resolution ? <span className={`finding-resolution ${resolution}`}><CheckIcon />{resolution === 'added' ? 'Added to patient record' : resolution === 'accepted' ? 'Accepted' : 'Rejected'}</span> : <>{onReject && <button className="reject-finding-button" onClick={() => onReject(event)} disabled={actionPending}><XIcon /> Reject finding</button>}{onApprove && <button className="approve-finding-button" onClick={() => onApprove(event)} disabled={actionPending}><CheckIcon /> {isSafetyEligible ? 'Add to patient record' : 'Accept finding'}</button>}</>}</div></div>
    {isBlocked && <div className="blocked-banner"><AlertIcon /><strong>This finding cannot be added to the patient record</strong><span>Safety status: {event.validation_status.replace(/_/g, ' ')}</span></div>}
  </article>
}

function AbbreviationSummary({ event, interpretation, interpretationResolution, needsReview, onUseSuggestion, onEditInterpretation, actionPending }: { event: ClinicalEvent; interpretation?: string; interpretationResolution?: 'confirmed' | 'corrected'; needsReview: boolean; onUseSuggestion?: (event: ClinicalEvent) => void; onEditInterpretation?: (event: ClinicalEvent) => void; actionPending: boolean }) {
  if (!event.ambiguous_abbreviation_resolved.was_ambiguous) return <div className="abbreviation-result"><span className="event-label">Abbreviation review</span>{needsReview ? <><span>Clinical interpretation needs review</span><small>Current interpretation: {event.processed_text}</small>{onEditInterpretation && <button className="interpretation-edit-button" onClick={() => onEditInterpretation(event)} disabled={actionPending}>Edit interpretation</button>}</> : <span>No ambiguity found</span>}</div>
  if (interpretation) return <div className="abbreviation-result"><span className="event-label">Abbreviation review</span><span>{interpretation}</span><small>{interpretationResolution ? 'Physician review recorded' : 'Physician corrected'}</small><button className="interpretation-edit-button" onClick={() => onEditInterpretation?.(event)} disabled={actionPending}>Edit interpretation</button></div>
  return <div className="abbreviation-result"><span className="event-label">Abbreviation review</span><span>Abbreviation needs review</span><small>Original: {event.original_text}</small><small>Suggested interpretation: {event.ambiguous_abbreviation_resolved.resolved_value ?? 'Not available'}</small><small>{formatConfidence(event.ambiguous_abbreviation_resolved.resolution_confidence)} resolution confidence</small><div className="interpretation-actions">{onUseSuggestion && <button className="suggestion-button" onClick={() => onUseSuggestion(event)} disabled={actionPending}>Use suggestion</button>}{onEditInterpretation && <button className="interpretation-edit-button" onClick={() => onEditInterpretation(event)} disabled={actionPending}>Edit interpretation</button>}</div></div>
}

function Detail({ label, value, mono = false, tone }: { label: string; value: string; mono?: boolean; tone?: 'negative' }) { return <div className="event-detail"><span>{label}</span><strong className={`${mono ? 'mono' : ''} ${tone ?? ''}`}>{value}</strong>{label === 'Standardized clinical concept' && <small>SNOMED CT</small>}</div> }
function AttributeSection({ title, items }: { title: string; items: Array<[string, string | null]> }) { return <div className="event-subsection"><span className="event-label">{title}</span><div className="attribute-grid">{items.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value ?? 'Not specified'}</strong></div>)}</div></div> }
function displayEntityType(entityType: string): string { return entityType === 'LabFinding' ? 'Laboratory finding' : entityType }
