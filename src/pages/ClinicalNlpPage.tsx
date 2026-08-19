import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useClinicalNlpOutput, useProcessClinicalNlp } from '../hooks/useStep2'
import { useRejectTier3 } from '../hooks/useMemory'
import { useWriteFinalizedMemory } from '../hooks/useDocuments'
import type { ClinicalEntityType, ClinicalEvent } from '../contracts/clinicalEvent'
import { useWorkflow, type WorkflowNavigationState } from '../context/WorkflowContext'
import { ClinicalEventCard, type ClinicalFindingResolution } from '../components/ClinicalEventCard'
import { ProvenanceDrawer } from '../components/ProvenanceDrawer'
import { SourceDocumentLink } from '../components/SourceDocumentLink'
import { SectionCard } from '../components/SectionCard'
import { WorkflowProgress } from '../components/WorkflowProgress'
import { AlertIcon, ArrowIcon, CheckIcon, SearchIcon, XIcon } from '../components/icons'
import { formatConfidence } from '../lib/confidence'

const entityTypes: Array<'All' | ClinicalEntityType> = ['All', 'Disease', 'Symptom', 'Medication', 'Allergy', 'Procedure', 'LabFinding', 'Dosage', 'Route']
type ReviewAction = { type: 'add' | 'accept' | 'reject'; event: ClinicalEvent }
type AbbreviationResolution = 'confirmed' | 'corrected'

export function ClinicalNlpPage() {
  const location = useLocation()
  const routeWorkflow = (location.state as WorkflowNavigationState | null)?.workflow
  const { workflow, setWorkflow } = useWorkflow()
  const { data: sourceData, isLoading } = useClinicalNlpOutput()
  const nlpProcess = useProcessClinicalNlp()
  const [selectedEntity, setSelectedEntity] = useState<'All' | ClinicalEntityType>('All')
  const [selectedEvent, setSelectedEvent] = useState<ClinicalEvent | null>(null)
  const [showAllFindings, setShowAllFindings] = useState(false)
  const [resolutions, setResolutions] = useState<Record<string, ClinicalFindingResolution>>({})
  const [interpretationCorrections, setInterpretationCorrections] = useState<Record<string, string>>({})
  const [abbreviationResolutions, setAbbreviationResolutions] = useState<Record<string, AbbreviationResolution>>({})
  const [pendingAction, setPendingAction] = useState<ReviewAction | null>(null)
  const [pendingInterpretation, setPendingInterpretation] = useState<ClinicalEvent | null>(null)
  const [interpretationInput, setInterpretationInput] = useState('')
  const [actionError, setActionError] = useState('')
  const writeMemory = useWriteFinalizedMemory()
  const rejectFinding = useRejectTier3()

  const nlpData = nlpProcess.data
  const nlpComplete = Boolean(nlpData)
  const sourceEvents = sourceData?.clinical_events ?? []
  const events = nlpData?.clinical_events ?? []
  const ambiguousEvents = sourceEvents.filter((event) => event.ambiguous_abbreviation_resolved.was_ambiguous)
  const pendingAbbreviationEvents = ambiguousEvents.filter((event) => !abbreviationResolutions[event.event_local_id])
  const reviewRequiredEvents = nlpComplete ? events.filter((event) => !resolutions[event.event_local_id] && requiresFindingReview(event, abbreviationResolutions)) : []
  const addedEvents = nlpComplete ? events.filter((event) => resolutions[event.event_local_id] === 'added') : []
  const acceptedEvents = nlpComplete ? events.filter((event) => resolutions[event.event_local_id] === 'accepted') : []
  const filteredEvents = useMemo(() => {
    const source = showAllFindings ? events : [...reviewRequiredEvents, ...addedEvents, ...acceptedEvents]
    return selectedEntity === 'All' ? source : source.filter((event) => event.entity_type === selectedEntity)
  }, [events, reviewRequiredEvents, addedEvents, acceptedEvents, selectedEntity, showAllFindings])
  const validEvents = nlpComplete ? events.filter((event) => event.validation_status === 'valid' || resolutions[event.event_local_id] === 'accepted') : []
  const readyForMemory = Boolean(nlpComplete && pendingAbbreviationEvents.length === 0 && reviewRequiredEvents.length === 0)
  const nlpProcessing = Boolean(sourceData && pendingAbbreviationEvents.length === 0 && !nlpComplete && !nlpProcess.isError)
  const sourceText = sourceEvents.map((event) => event.original_text).join(' Â· ')
  const reviewText = reviewRequiredEvents.length === 0 ? 'No findings require your review' : `${reviewRequiredEvents.length} ${reviewRequiredEvents.length === 1 ? 'finding needs' : 'findings need'} your review`
  const actionPending = writeMemory.isPending || rejectFinding.isPending

  useEffect(() => {
    if (routeWorkflow && routeWorkflow.document_id !== workflow.document_id) setWorkflow(routeWorkflow)
  }, [location.state])

  useEffect(() => {
    if (!sourceData || pendingAbbreviationEvents.length > 0 || nlpProcess.data || nlpProcess.isFetching || nlpProcess.isError) return
    void nlpProcess.refetch()
  }, [sourceData, pendingAbbreviationEvents.length, nlpProcess.data, nlpProcess.isFetching, nlpProcess.isError])

  useEffect(() => {
    if (!sourceData) return
    setWorkflow({
      patient_id: sourceData.patient_id,
      encounter_id: sourceData.encounter_id,
      document_id: sourceData.source_document_id,
      abbreviation_review_status: pendingAbbreviationEvents.length === 0 ? 'complete' : 'pending',
      nlp_status: nlpComplete ? 'complete' : nlpProcess.isError ? 'failed' : pendingAbbreviationEvents.length === 0 ? 'processing' : 'pending',
      clinical_finding_review_status: nlpComplete && reviewRequiredEvents.length === 0 ? 'complete' : 'pending',
      safety_status: readyForMemory ? 'ready' : 'blocked',
      current_stage: pendingAbbreviationEvents.length > 0 ? 'abbreviation-review' : !nlpComplete ? 'nlp-processing' : reviewRequiredEvents.length > 0 ? 'finding-review' : readyForMemory ? 'patient-memory' : 'safety-check',
    })
  }, [sourceData, pendingAbbreviationEvents.length, reviewRequiredEvents.length, readyForMemory, nlpComplete, nlpProcess.isError])

  const openReviewAction = (type: ReviewAction['type'], event: ClinicalEvent) => {
    setActionError('')
    setPendingAction({ type, event })
  }

  const openInterpretationEditor = (event: ClinicalEvent) => {
    setInterpretationInput(interpretationCorrections[event.event_local_id] ?? event.ambiguous_abbreviation_resolved.resolved_value ?? event.processed_text)
    setPendingInterpretation(event)
  }

  const useSuggestion = (event: ClinicalEvent) => {
    const suggestion = event.ambiguous_abbreviation_resolved.resolved_value
    if (!suggestion) return
    setInterpretationCorrections((current) => ({ ...current, [event.event_local_id]: suggestion }))
    setAbbreviationResolutions((current) => ({ ...current, [event.event_local_id]: 'confirmed' }))
  }

  const saveInterpretation = () => {
    if (!pendingInterpretation || !interpretationInput.trim()) return
    setInterpretationCorrections((current) => ({ ...current, [pendingInterpretation.event_local_id]: interpretationInput.trim() }))
    if (pendingInterpretation.ambiguous_abbreviation_resolved.was_ambiguous) setAbbreviationResolutions((current) => ({ ...current, [pendingInterpretation.event_local_id]: 'corrected' }))
    setPendingInterpretation(null)
  }

  const correctedEventForWrite = (event: ClinicalEvent): ClinicalEvent => {
    const correction = interpretationCorrections[event.event_local_id]
    if (!correction) return event
    return { ...event, processed_text: correction, ambiguous_abbreviation_resolved: { ...event.ambiguous_abbreviation_resolved, resolved_value: correction, was_ambiguous: false }, medication_attributes: event.medication_attributes.frequency ? { ...event.medication_attributes, frequency: correction } : event.medication_attributes }
  }

  const confirmReviewAction = () => {
    if (!pendingAction || !nlpData) return
    if (pendingAction.type === 'add' || pendingAction.type === 'accept') {
      const resolution = pendingAction.type === 'accept' ? 'accepted' : 'added'
      writeMemory.mutate({ patient_id: nlpData.patient_id, encounter_id: nlpData.encounter_id, source: 'physician_approved_consultation', clinical_events: [correctedEventForWrite(pendingAction.event)] }, { onSuccess: () => { setResolutions((current) => ({ ...current, [pendingAction.event.event_local_id]: resolution })); setPendingAction(null) }, onError: () => setActionError(pendingAction.type === 'accept' ? 'Unable to accept this finding. Try again.' : 'Unable to add this finding. Try again.') })
    } else {
      rejectFinding.mutate({ eventId: pendingAction.event.event_local_id, physicianId: 'phy_04' }, { onSuccess: () => { setResolutions((current) => ({ ...current, [pendingAction.event.event_local_id]: 'rejected' })); setPendingAction(null) }, onError: () => setActionError('Unable to reject this finding. Try again.') })
    }
  }

  return <div className="page-stack">
    <div className="page-heading"><div><p className="eyebrow">CLINICAL ANALYSIS</p><h1>Clinical intelligence</h1><p className="page-subtitle">Review extracted information, clinical findings, and safety checks before opening patient memory.</p></div><div className="nlp-job-meta"><span className="live-dot" /><div><strong>{nlpProcessing ? 'NLP processing' : nlpProcess.isError ? 'NLP processing unavailable' : nlpComplete ? 'Analysis complete' : 'Loading analysis'}</strong><span>{nlpData?.processed_at ? `Processed ${new Date(nlpData.processed_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) }` : nlpProcessing ? 'Entity extraction and clinical context in progress' : 'Loading abbreviation review'}</span></div></div></div>
    <WorkflowProgress detail />
    <div className="clinical-context-strip"><span>Patient <strong>{sourceData?.patient_id ?? workflow.patient_id}</strong></span><span>Document <strong>{sourceData?.source_document_id ?? workflow.document_id}</strong></span></div>

    {nlpComplete && <details className="section-card text-view-card nlp-collapsible">
      <summary className="section-card-header nlp-collapsible-summary"><div><p className="eyebrow">EXTRACTED INFORMATION</p><h2>Review the extracted information against the original source document.</h2></div><span className="text-link">Show extracted info & attached source <ArrowIcon /></span></summary>
      <div className="nlp-collapsible-body"><div className="text-view-meta"><SourceDocumentAttachment documentId={sourceData?.source_document_id ?? workflow.document_id} /><span>Patient {sourceData?.patient_id ?? workflow.patient_id}</span></div><div className="text-view-block"><span className="text-view-label">Extracted text</span><p className="highlighted-text">{isLoading ? 'Loading source information...' : <EntityHighlightedText events={events} text={sourceText} />}</p></div></div>
    </details>}

    <AbbreviationReview events={ambiguousEvents} loading={isLoading} resolutions={abbreviationResolutions} interpretations={interpretationCorrections} onUseSuggestion={useSuggestion} onEditInterpretation={openInterpretationEditor} />

    {!nlpComplete ? <ClinicalFindingsGate abbreviationReady={pendingAbbreviationEvents.length === 0} processing={nlpProcessing} error={nlpProcess.isError} /> : <SectionCard title="Clinical findings" eyebrow={reviewText.toUpperCase()} action={<div className="event-tools"><div className="search-box"><SearchIcon /><input placeholder="Search findings" aria-label="Search clinical findings" /></div><button className="clear-filter" onClick={() => setSelectedEntity('All')}>{selectedEntity === 'All' ? 'All finding types' : displayEntityType(selectedEntity)} âŒ„</button></div>}>
      <p className="findings-subtitle">Review the clinical findings identified from the processed information.</p><p className="findings-review-count">{reviewText}</p><div className="entity-filter-row">{entityTypes.map((type) => <button key={type} onClick={() => setSelectedEntity(type)} className={selectedEntity === type ? 'entity-filter active' : 'entity-filter'}>{type === 'LabFinding' ? 'Laboratory finding' : type === 'All' ? 'All findings' : type}</button>)}</div>{filteredEvents.length > 0 ? <div className="clinical-event-list">{filteredEvents.map((event) => <ClinicalEventCard key={event.event_local_id} event={event} onProvenance={setSelectedEvent} onApprove={(finding) => openReviewAction(finding.validation_status === 'valid' ? 'add' : 'accept', finding)} onReject={(finding) => openReviewAction('reject', finding)} onUseSuggestion={useSuggestion} onEditInterpretation={openInterpretationEditor} interpretation={interpretationCorrections[event.event_local_id]} interpretationResolution={abbreviationResolutions[event.event_local_id]} resolution={resolutions[event.event_local_id]} actionPending={actionPending} />)}</div> : <div className="empty-loading">All findings reviewed</div>}<button className="clinical-findings-toggle" aria-expanded={showAllFindings} onClick={() => { setShowAllFindings((current) => !current); if (!showAllFindings) setSelectedEntity('All') }}>{showAllFindings ? 'Hide additional findings' : 'View all clinical findings'} <ArrowIcon /></button>
    </SectionCard>}

    {pendingAbbreviationEvents.length === 0 && !nlpComplete && <NlpProcessingState error={nlpProcess.isError} />}
    {nlpComplete && <SafetyCheck ready={readyForMemory} pendingAbbreviations={pendingAbbreviationEvents.length} pendingFindings={reviewRequiredEvents.length} />}
    {nlpComplete && <MemoryHandoff events={validEvents} totalEvents={events.length} ready={readyForMemory} patientId={nlpData?.patient_id ?? workflow.patient_id} encounterId={nlpData?.encounter_id ?? workflow.encounter_id} documentId={nlpData?.source_document_id ?? workflow.document_id} onEventClick={setSelectedEvent} />}
    {selectedEvent && <ProvenanceDrawer event={selectedEvent} onClose={() => setSelectedEvent(null)} />}
    {pendingAction && <ReviewConfirmationDialog action={pendingAction} isPending={actionPending} error={actionError} onCancel={() => { if (!actionPending) setPendingAction(null) }} onConfirm={confirmReviewAction} />}
    {pendingInterpretation && <InterpretationCorrectionDialog event={pendingInterpretation} value={interpretationInput} onChange={setInterpretationInput} onCancel={() => setPendingInterpretation(null)} onSave={saveInterpretation} />}
  </div>
}

function SourceDocumentAttachment({ documentId }: { documentId: string }) { return <SourceDocumentLink documentId={documentId} className="text-view-source-reference" label="Open attached record" /> }

function AbbreviationReview({ events, loading, resolutions, interpretations, onUseSuggestion, onEditInterpretation }: { events: ClinicalEvent[]; loading: boolean; resolutions: Record<string, AbbreviationResolution>; interpretations: Record<string, string>; onUseSuggestion: (event: ClinicalEvent) => void; onEditInterpretation: (event: ClinicalEvent) => void }) {
  const pendingCount = events.filter((event) => !resolutions[event.event_local_id]).length
  return <SectionCard title="Abbreviation review" eyebrow="REVIEW BEFORE CLINICAL FINDINGS" action={<span className="review-heading"><AlertIcon /> {pendingCount} to review</span>} className="abbreviation-review-card"><p className="abbreviation-review-subtitle">Confirm ambiguous abbreviations before reviewing the clinical findings.</p>{loading ? <div className="empty-loading">Loading abbreviation reviewâ€¦</div> : events.length === 0 ? <div className="empty-loading">No ambiguous abbreviations identified.</div> : <div className="abbreviation-review-list">{events.map((event) => { const interpretation = interpretations[event.event_local_id] ?? event.ambiguous_abbreviation_resolved.resolved_value ?? event.processed_text; const resolution = resolutions[event.event_local_id]; return <article className="abbreviation-review-item" key={event.event_local_id}><div className="abbreviation-review-copy"><span className="event-label">Original</span><strong>{event.original_text}</strong><span className="event-label">Suggested interpretation</span><p>{interpretation}</p><span className="event-label">Confidence</span><p>{formatConfidence(event.ambiguous_abbreviation_resolved.resolution_confidence)}</p><small>Source text is preserved Â· {event.source_document_id}</small></div><div className="abbreviation-review-actions">{resolution && <span className={`abbreviation-resolution ${resolution}`}><CheckIcon /> Physician {resolution}</span>}{!resolution && event.ambiguous_abbreviation_resolved.resolved_value && <button className="suggestion-button" onClick={() => onUseSuggestion(event)}>Use suggestion</button>}<button className="interpretation-edit-button" onClick={() => onEditInterpretation(event)}>Edit interpretation</button></div></article> })}</div>}</SectionCard>
}

function ClinicalFindingsGate({ abbreviationReady, processing, error }: { abbreviationReady: boolean; processing: boolean; error: boolean }) {
  const message = error ? 'NLP processing could not be completed. Clinical findings remain unavailable.' : abbreviationReady && processing ? 'NLP processing is in progress. Clinical findings will appear after entity extraction and clinical context are complete.' : 'Complete abbreviation review before clinical findings can be generated.'
  return <SectionCard title="Clinical findings" eyebrow={error ? 'PROCESSING ERROR' : abbreviationReady ? 'NLP PROCESSING' : 'WAITING FOR ABBREVIATION REVIEW'} action={<span className="high-risk-label"><AlertIcon /> {error ? 'Unavailable' : 'Waiting'}</span>}><div className="clinical-findings-gate" role="status"><strong>{error ? 'Clinical findings are not ready yet' : abbreviationReady && processing ? 'Clinical findings are being generated' : 'Clinical findings are not ready yet'}</strong><p>{message}</p><small>Findings are not displayed until abbreviation review and NLP processing are complete.</small></div></SectionCard>
}

function NlpProcessingState({ error }: { error: boolean }) {
  return <SectionCard title="NLP processing" eyebrow="CLINICAL INTELLIGENCE" action={error ? <span className="high-risk-label"><AlertIcon /> Review required</span> : <span className="review-heading"><span className="live-dot" /> Processing</span>}><div className="clinical-findings-gate" role="status"><strong>{error ? 'NLP processing could not be completed' : 'Entity extraction and clinical context in progress'}</strong><p>{error ? 'The clinical findings are still unavailable. Review the processing status before continuing.' : 'BioClinicalBERT entity extraction and LLM clinical contextualization are running automatically.'}</p><small>Clinical findings will appear after processing finishes successfully.</small></div></SectionCard>
}

function SafetyCheck({ ready, pendingAbbreviations, pendingFindings }: { ready: boolean; pendingAbbreviations: number; pendingFindings: number }) {
  return <SectionCard title="Safety check" eyebrow="MEMORY WRITE SAFEGUARD" action={ready ? <span className="verified-heading"><CheckIcon /> Ready</span> : <span className="high-risk-label"><AlertIcon /> Review required</span>} className={ready ? 'safety-check-card safety-ready' : 'safety-check-card'}><p>{ready ? 'All required abbreviation and clinical finding reviews are complete. Findings may be reviewed before patient memory is opened.' : `${pendingAbbreviations} abbreviation review${pendingAbbreviations === 1 ? '' : 's'} and ${pendingFindings} clinical finding${pendingFindings === 1 ? '' : 's'} still require physician attention.`}</p><small>Automated safety warnings require an explicit physician decision before memory access.</small></SectionCard>
}

function ReviewConfirmationDialog({ action, isPending, error, onCancel, onConfirm }: { action: ReviewAction; isPending: boolean; error: string; onCancel: () => void; onConfirm: () => void }) { const adding = action.type === 'add'; const accepting = action.type === 'accept'; return <div className="drawer-backdrop" role="presentation"><div className="confirmation-dialog" role="dialog" aria-modal="true" aria-labelledby="review-confirmation-title"><button className="confirmation-close" aria-label="Close confirmation" onClick={onCancel} disabled={isPending}><XIcon /></button><p className="eyebrow">PHYSICIAN REVIEW</p><h2 id="review-confirmation-title">{adding ? 'Add this finding to the patient record?' : accepting ? 'Accept this finding?' : 'Reject this finding?'}</h2><p>{adding ? "This finding has passed the current safety checks and can be added to the patient's clinical record." : accepting ? 'Your review will accept this finding and make it available for the patient record.' : 'This finding will not be added to the patient record.'}</p><div className="confirmation-actions"><button className="secondary-button" onClick={onCancel} disabled={isPending}>Cancel</button><button className={adding || accepting ? 'approve-finding-button' : 'reject-finding-button'} onClick={onConfirm} disabled={isPending}>{isPending ? 'Savingâ€¦' : adding ? 'Add to patient record' : accepting ? 'Accept finding' : 'Reject finding'}</button></div>{error && <p className="error-copy"><AlertIcon /> {error}</p>}</div></div> }

function InterpretationCorrectionDialog({ event, value, onChange, onCancel, onSave }: { event: ClinicalEvent; value: string; onChange: (value: string) => void; onCancel: () => void; onSave: () => void }) { const ambiguous = event.ambiguous_abbreviation_resolved.was_ambiguous; return <div className="drawer-backdrop" role="presentation"><div className="confirmation-dialog interpretation-dialog" role="dialog" aria-modal="true" aria-labelledby="interpretation-title"><button className="confirmation-close" aria-label="Close interpretation correction" onClick={onCancel}><XIcon /></button><p className="eyebrow">PHYSICIAN REVIEW</p><h2 id="interpretation-title">{ambiguous ? 'Correct abbreviation' : 'Correct clinical interpretation'}</h2><div className="interpretation-summary"><span>Original</span><strong>{event.original_text}</strong><span>Suggested</span><strong>{event.ambiguous_abbreviation_resolved.resolved_value ?? event.processed_text}</strong></div><label>Interpretation<input aria-label="Interpretation" value={value} onChange={(input) => onChange(input.target.value)} /></label><div className="confirmation-actions"><button className="secondary-button" onClick={onCancel}>Cancel</button><button className="approve-finding-button" onClick={onSave} disabled={!value.trim()}><CheckIcon /> Save correction</button></div></div></div> }

function EntityHighlightedText({ events, text }: { events: ClinicalEvent[]; text: string }) { if (!text) return <>â€”</>; const sorted = [...events].sort((a, b) => a.source_text_span.start - b.source_text_span.start); const pieces: Array<{ text: string; event?: ClinicalEvent }> = []; let cursor = 0; sorted.forEach((event) => { const start = Math.max(cursor, event.source_text_span.start); const end = Math.min(text.length, Math.max(start, event.source_text_span.end)); if (start > cursor) pieces.push({ text: text.slice(cursor, start) }); if (end > start) pieces.push({ text: text.slice(start, end), event }); cursor = end }); if (cursor < text.length) pieces.push({ text: text.slice(cursor) }); return <>{pieces.map((piece, index) => piece.event ? <mark key={`${piece.event.event_local_id}-${index}`} className={`entity-highlight entity-${piece.event.entity_type.toLowerCase()}`} title={displayEntityType(piece.event.entity_type)}>{piece.text}</mark> : <span key={`text-${index}`}>{piece.text}</span>)}</> }

function MemoryHandoff({ events, totalEvents, ready, patientId, encounterId, documentId, onEventClick }: { events: ClinicalEvent[]; totalEvents: number; ready: boolean; patientId: string; encounterId: string; documentId: string; onEventClick: (event: ClinicalEvent) => void }) {
  const nextWorkflow = { patient_id: patientId, encounter_id: encounterId, document_id: documentId, current_stage: 'patient-memory' as const, processing_status: 'complete' as const, abbreviation_review_status: 'complete' as const, nlp_status: 'complete' as const, clinical_finding_review_status: 'complete' as const, safety_status: 'ready' as const }
  return <section className={`memory-handoff ${ready ? '' : 'memory-handoff-blocked'}`}><div className="handoff-icon">{ready ? <ArrowIcon /> : <AlertIcon />}</div><div className="handoff-copy"><p className="eyebrow">CLINICAL FINDINGS â†’ PATIENT MEMORY</p><h2>{ready ? 'Ready for patient memory' : 'Review required before patient memory'}</h2>{!ready && <strong className="handoff-valid-label">Ready to add to patient record</strong>}<p>{ready ? `${events.length} ${events.length === 1 ? 'finding is' : 'findings are'} ready for patient memory after the safety check.` : `${events.filter((event) => event.validation_status === 'valid').length} valid findings are ready to add to the patient record after required review.`}</p></div><div className="handoff-events">{events.slice(0, 4).map((event) => <button key={event.event_local_id} onClick={() => onEventClick(event)}><span className={`entity-key entity-${event.entity_type.toLowerCase()}`} />{event.normalized_concept}<small>{event.event_local_id}</small></button>)}{events.length > 4 && <span className="more-events">+{events.length - 4} more</span>}</div><div className="handoff-count"><strong>{events.length}</strong><span>of {totalEvents} cleared</span></div>{ready ? <Link className="handoff-button" to="/memory" state={{ workflow: nextWorkflow }}>Open patient memory <ArrowIcon /></Link> : <button className="handoff-button" disabled>Open patient memory <ArrowIcon /></button>}</section>
}

function displayEntityType(entityType: string): string { return entityType === 'LabFinding' ? 'Laboratory finding' : entityType }

function requiresFindingReview(event: ClinicalEvent, abbreviationResolutions: Record<string, AbbreviationResolution>) {
  return event.validation_status !== 'valid' || event.gemini_contextualization_confidence < 0.8 || (event.ambiguous_abbreviation_resolved.was_ambiguous && !abbreviationResolutions[event.event_local_id])
}
