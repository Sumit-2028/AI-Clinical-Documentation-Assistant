import { useEffect, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import type { Conflict } from '../contracts/retrievedContext'
import type { MemoryFact } from '../contracts/memory'
import { useConflictList } from '../hooks/useMemory'
import { usePatientRecord } from '../hooks/usePatients'
import { useWorkflow, type WorkflowNavigationState } from '../context/WorkflowContext'
import { useConflictResolutions, type ConflictResolutionAction } from '../context/ConflictResolutionContext'
import { TrustTierBadge } from '../components/Badges'
import { SectionCard } from '../components/SectionCard'
import { SourceDocumentLink } from '../components/SourceDocumentLink'
import { AlertIcon, ArrowIcon, CheckIcon } from '../components/icons'

export function ResolveConflictPage() {
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const routeState = location.state as WorkflowNavigationState | null
  const { workflow, setWorkflow } = useWorkflow()
  const patientId = routeState?.patient?.patient_id ?? searchParams.get('patient_id') ?? routeState?.workflow?.patient_id ?? workflow.patient_id
  const patientRecord = usePatientRecord(patientId)
  const patient = patientRecord.data ?? routeState?.patient
  const { data: conflicts = [], isLoading } = useConflictList(patientId)
  const { resolutions, resolveConflict } = useConflictResolutions()
  const requestedConflictId = searchParams.get('conflict_id')
  const conflict = conflicts.find((item) => item.conflict_id === requestedConflictId) ?? conflicts.find((item) => item.status === 'unresolved') ?? conflicts[0]
  const [savedAction, setSavedAction] = useState<ConflictResolutionAction | null>(null)

  useEffect(() => {
    if (routeState?.workflow && routeState.workflow.patient_id !== workflow.patient_id) setWorkflow(routeState.workflow)
    if (patient && (patient.patient_id !== workflow.patient_id || patient.encounter_id !== workflow.encounter_id)) setWorkflow({ ...workflow, patient_id: patient.patient_id, encounter_id: patient.encounter_id })
  }, [location.state, patient])

  useEffect(() => {
    if (conflict) setSavedAction(resolutions[conflict.conflict_id]?.action ?? null)
  }, [conflict, resolutions])

  const memoryHref = `/memory?patient_id=${encodeURIComponent(patientId)}`
  const saveResolution = (action: ConflictResolutionAction) => {
    if (!conflict) return
    resolveConflict(conflict, action)
    setSavedAction(action)
  }

  return <div className="page-stack resolve-conflict-page">
    <div className="page-heading"><div><p className="eyebrow">SAFETY REVIEW</p><h1>Resolve conflict</h1><p className="page-subtitle">Review both clinical records before deciding which information should remain active for this patient.</p></div><Link className="memory-context-back" to={memoryHref} state={{ workflow: { ...workflow, patient_id: patientId, current_stage: 'patient-memory' as const }, patient }}><ArrowIcon /> Back to patient memory</Link></div>
    <div className="resolve-patient-context"><span>Patient <strong>{patient?.name ?? 'Patient record'}</strong></span><span>Patient ID <strong>{patientId}</strong></span></div>
    {isLoading ? <div className="empty-loading">Loading conflict details…</div> : !conflict ? <SectionCard title="Conflict unavailable" eyebrow="SAFETY REVIEW"><p className="resolve-empty-copy">This conflict is no longer available in the active review list.</p><Link className="primary-button resolve-return-button" to={memoryHref} state={{ workflow: { ...workflow, patient_id: patientId, current_stage: 'patient-memory' as const }, patient }}>Return to Patient Memory <ArrowIcon /></Link></SectionCard> : <>
      <SectionCard title="Conflict summary" eyebrow="PHYSICIAN DECISION REQUIRED" className="conflict-summary-card"><div className="resolve-summary-grid"><div><span>Conflict ID</span><strong>{conflict.conflict_id}</strong></div><div><span>Conflict type</span><strong>{formatConflictType(conflict)}</strong></div><div><span>Safety priority</span><strong className="resolve-risk"><AlertIcon /> {conflict.risk_level}</strong></div><div><span>Concept thread</span><strong>{conflict.concept_thread}</strong></div></div></SectionCard>
      <SectionCard title="Conflicting clinical records" eyebrow="COMPARE SOURCE AND TRUST"><div className="resolve-record-grid"><ConflictRecord fact={conflict.event_a} label="Record 1" /><div className="resolve-vs">VS</div><ConflictRecord fact={conflict.event_b} label="Record 2" /></div></SectionCard>
      <SectionCard title="Relevant clinical context" eyebrow="WHY THIS NEEDS REVIEW" className="resolve-context-card"><div className="resolve-context-copy"><AlertIcon /><p>These records describe the same clinical thread but disagree. The verified record and unverified information remain separate until the physician records a decision.</p></div><div className="resolve-context-thread"><span>Clinical thread</span><strong>{conflict.concept_thread}</strong></div></SectionCard>
      <SectionCard title="Resolution actions" eyebrow="RECORD PHYSICIAN DECISION" className="resolve-actions-card"><p className="resolve-action-copy">Choose the outcome for this conflict. The decision will remove it from the active Needs Review list.</p><div className="resolve-action-grid"><button className="resolve-action-button verified-action" onClick={() => saveResolution('keep_record_1')} disabled={Boolean(savedAction)}><CheckIcon /> Keep Record 1</button><button className="resolve-action-button unverified-action" onClick={() => saveResolution('keep_record_2')} disabled={Boolean(savedAction)}><CheckIcon /> Keep Record 2</button><button className="resolve-action-button neutral-action" onClick={() => saveResolution('mark_resolved')} disabled={Boolean(savedAction)}><CheckIcon /> Mark as Resolved</button><button className="resolve-action-button reject-action" onClick={() => saveResolution('reject_record_2')} disabled={Boolean(savedAction)}><AlertIcon /> Reject/Discard conflicting information</button></div>{savedAction && <div className="resolve-success" role="status"><CheckIcon /><span><strong>{resolutionLabel(savedAction)}</strong><small>Conflict removed from active Needs Review.</small></span></div>}<Link className="primary-button resolve-return-button" to={memoryHref} state={{ workflow: { ...workflow, patient_id: patientId, current_stage: 'patient-memory' as const }, patient }}>Return to Patient Memory <ArrowIcon /></Link></SectionCard>
    </>}
  </div>
}

function ConflictRecord({ fact, label }: { fact: MemoryFact; label: string }) {
  const verified = fact.trust_tier < 3
  return <article className={`resolve-record ${verified ? 'verified-record' : 'unverified-record'}`}><div className="resolve-record-heading"><div><span className="resolve-record-label">{label} — {verified ? 'Verified' : 'Unverified'}</span><h3>{fact.normalized_concept}</h3></div><div className="resolve-record-header-actions"><TrustTierBadge tier={fact.trust_tier} /><SourceDocumentLink documentId={fact.source_document_id} className="resolve-header-source-action" label="Open Attached Record" showDocument={false} /></div></div><div className="resolve-record-details"><div><span>Clinical finding</span><strong>{fact.assertion}</strong></div><div><span>Clinical status</span><strong>{fact.clinical_status}</strong></div><div><span>Source information</span><SourceDocumentLink documentId={fact.source_document_id} className="resolve-source-document" label="Open Attached Record" showAction={false} /></div><div><span>Source text position</span><strong>{fact.source_text_span.start}–{fact.source_text_span.end}</strong></div><div><span>Input type</span><strong>{fact.input_modality}</strong></div><div><span>Language</span><strong>{fact.source_language.toUpperCase()}</strong></div></div><p className="resolve-record-note">{verified ? 'Verified record' : 'Unverified information'}</p></article>
}

function formatConflictType(conflict: Conflict): string {
  if (conflict.conflict_type) return conflict.conflict_type.replace(/_/g, ' ')
  return conflict.concept_thread === 'drug_allergy' ? 'Assertion mismatch' : 'Clinical record conflict'
}

function resolutionLabel(action: ConflictResolutionAction): string {
  return { keep_record_1: 'Record 1 kept', keep_record_2: 'Record 2 kept', mark_resolved: 'Conflict marked as resolved', reject_record_2: 'Conflicting information discarded' }[action]
}
