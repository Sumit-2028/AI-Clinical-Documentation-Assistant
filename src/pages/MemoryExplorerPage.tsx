import { useEffect, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import type { MemoryFact } from '../contracts/memory'
import type { Conflict, RetrievedContext } from '../contracts/retrievedContext'
import { useApproveTier3, useConflictList, useMemoryEvents, useRejectTier3, useResolveConflict, useRetrievedContext } from '../hooks/useMemory'
import { useWorkflow, type WorkflowNavigationState } from '../context/WorkflowContext'
import { useConflictResolutions } from '../context/ConflictResolutionContext'
import { usePatientRecord } from '../hooks/usePatients'
import type { PatientRecord } from '../contracts/patient'
import { TrustTierBadge } from '../components/Badges'
import { MemoryFactCard } from '../components/MemoryFactCard'
import { MemoryProvenanceDrawer } from '../components/MemoryProvenanceDrawer'
import { SectionCard } from '../components/SectionCard'
import { AlertIcon, ArrowIcon, CheckIcon, ClockIcon, FileIcon, HeartIcon, SearchIcon, XIcon } from '../components/icons'

type MemoryView = 'memory' | 'timeline' | 'verified' | 'unverified' | 'conflicts'
const contextCategories = ['conditions', 'medications', 'allergies', 'procedures', 'lab_trends', 'significant_events'] as const
const categoryLabels: Record<typeof contextCategories[number], string> = { conditions: 'Conditions', medications: 'Medications', allergies: 'Allergies', procedures: 'Procedures', lab_trends: 'Laboratory trends', significant_events: 'Significant events' }
const queryStopWords = new Set(['what', 'would', 'like', 'know', 'about', 'this', 'patient', 'patients', 'the', 'their', 'has', 'have', 'been', 'are', 'any', 'for', 'from', 'with', 'that', 'today', 'visit', 'recent', 'currently', 'relevant', 'history'])

export function deriveQueryConcepts(question: string): string[] {
  const normalized = question.toLowerCase().replace(/[^a-z0-9\s-]/g, ' ')
  const concepts = [
    ['chest pain', 'chest pain'], ['hypertension', 'hypertension'], ['high blood pressure', 'hypertension'],
    ['medication changes', 'medication changes'], ['medication change', 'medication changes'], ['medications', 'medications'], ['medication', 'medications'], ['meds', 'medications'],
    ['allergy history', 'allergies'], ['allergies', 'allergies'], ['allergy', 'allergies'], ['procedures', 'procedures'], ['procedure', 'procedures'],
  ].filter(([phrase]) => normalized.includes(phrase)).map(([, concept]) => concept)
  const words = normalized.split(/\s+/).filter((word) => word.length > 3 && !queryStopWords.has(word))
  return [...new Set([...concepts, ...words])].slice(0, 8)
}

export function MemoryExplorerPage({ initialView = 'memory' }: { initialView?: MemoryView }) {
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const { workflow, setWorkflow } = useWorkflow()
  const routeWorkflow = (location.state as WorkflowNavigationState | null)?.workflow
  const routePatient = (location.state as WorkflowNavigationState | null)?.patient
  const [view, setView] = useState<MemoryView>(initialView)
  const [queryInput, setQueryInput] = useState('')
  const [submittedQuestion, setSubmittedQuestion] = useState('')
  const [submittedConcepts, setSubmittedConcepts] = useState(['chest pain'])
  const [hasSearched, setHasSearched] = useState(true)
  const [conversation, setConversation] = useState<string[]>([])
  const [patientId] = useState(() => routePatient?.patient_id ?? searchParams.get('patient_id') ?? routeWorkflow?.patient_id ?? workflow.patient_id)
  const patientRecord = usePatientRecord(patientId)
  const resolvedPatient = patientRecord.data ?? routePatient
  const encounterId = resolvedPatient?.encounter_id ?? routeWorkflow?.encounter_id ?? workflow.encounter_id
  const [selectedFact, setSelectedFact] = useState<MemoryFact | null>(null)
  const [approvedIds, setApprovedIds] = useState<string[]>([])
  const [rejectedIds, setRejectedIds] = useState<string[]>([])
  const [resolvedIds, setResolvedIds] = useState<string[]>([])
  const { data: context, isLoading } = useRetrievedContext(submittedConcepts, patientId, encounterId)
  const { data: timeline = [] } = useMemoryEvents(patientId)
  const { data: conflicts = [] } = useConflictList(patientId)
  const approve = useApproveTier3()
  const reject = useRejectTier3()
  const resolve = useResolveConflict()
  const { isResolved, resolveConflict: recordConflictResolution } = useConflictResolutions()
  const displayedContext = applyTierActions(context, approvedIds, rejectedIds)
  const activeConflicts = conflicts.filter((conflict) => !isResolved(conflict.conflict_id))
  const activeContextConflicts = (context?.conflicts ?? conflicts).filter((conflict) => !isResolved(conflict.conflict_id))

  useEffect(() => {
    if (routeWorkflow && (routeWorkflow.patient_id !== workflow.patient_id || routeWorkflow.encounter_id !== workflow.encounter_id || routeWorkflow.document_id !== workflow.document_id)) setWorkflow(routeWorkflow)
    if (resolvedPatient && (resolvedPatient.patient_id !== workflow.patient_id || resolvedPatient.encounter_id !== workflow.encounter_id)) setWorkflow({ patient_id: resolvedPatient.patient_id, encounter_id: resolvedPatient.encounter_id })
  }, [location.state, resolvedPatient])

  const submitQuery = (question: string) => {
    const trimmed = question.trim()
    if (!trimmed) return
    setConversation((turns) => [...turns, trimmed])
    setSubmittedQuestion(trimmed)
    setSubmittedConcepts(deriveQueryConcepts(trimmed))
    setHasSearched(true)
    setQueryInput('')
  }
  const approveFact = (fact: MemoryFact) => { setApprovedIds((ids) => [...ids, fact.event_id]); approve.mutate({ eventId: fact.event_id, physicianId: 'phy_04' }) }
  const rejectFact = (fact: MemoryFact) => { setRejectedIds((ids) => [...ids, fact.event_id]); reject.mutate({ eventId: fact.event_id, physicianId: 'phy_04' }) }
  const resolveConflict = (conflictId: string, action: 'confirm_event_a' | 'confirm_event_b' | 'keep_unresolved') => { const conflict = conflicts.find((item) => item.conflict_id === conflictId); if (conflict) recordConflictResolution(conflict, action === 'confirm_event_a' ? 'keep_record_1' : action === 'confirm_event_b' ? 'keep_record_2' : 'mark_resolved'); setResolvedIds((ids) => [...ids, conflictId]); resolve.mutate({ conflictId, request: { resolution_action: action, physician_id: 'phy_04' } }) }

  return <div className="page-stack">
    <PatientMemoryHeader patient={resolvedPatient} patientId={patientId} />
    <MemoryTabs view={view} onChange={setView} />
    {view === 'memory' && <><ClinicalQueryPanel query={queryInput} setQuery={setQueryInput} onSubmit={submitQuery} conversation={conversation} patient={resolvedPatient} patientId={patientId} /><MemoryWorkspace context={displayedContext} timeline={timeline} conflicts={activeContextConflicts} question={submittedQuestion} hasSearched={hasSearched} isLoading={isLoading || patientRecord.isLoading} patientId={patientId} onFactClick={setSelectedFact} onApprove={approveFact} onReject={rejectFact} /></>}
    {view === 'timeline' && <TimelineView events={timeline} onFactClick={setSelectedFact} />}
    {view === 'verified' && <VerifiedInformationTab context={displayedContext} onFactClick={setSelectedFact} />}
    {view === 'unverified' && <UnverifiedInformationTab context={displayedContext} onFactClick={setSelectedFact} onApprove={approveFact} onReject={rejectFact} />}
    {view === 'conflicts' && <><div className="conflict-route-header"><Link className="memory-context-back" to={`/memory?patient_id=${encodeURIComponent(patientId)}`}><ArrowIcon /> Back to patient memory</Link></div><ConflictCenter conflicts={conflicts} resolvedIds={resolvedIds} onResolve={resolveConflict} onFactClick={setSelectedFact} /></>}
    {selectedFact && <MemoryProvenanceDrawer fact={selectedFact} onClose={() => setSelectedFact(null)} />}
  </div>
}

function PatientMemoryHeader({ patient, patientId }: { patient?: PatientRecord; patientId: string }) {
  const name = patient?.name ?? 'Patient record'
  const initials = name === 'Patient record' ? 'P' : name.split(' ').map((part) => part[0]).join('').slice(0, 2)
  return <div className="memory-header"><div className="patient-profile-large"><div className="patient-avatar-large">{initials}</div><div><p className="eyebrow">PATIENT MEMORY</p><h1>{name}</h1><p>{patient ? `${patient.age} years · ${patient.gender} · ` : ''}<span className="patient-status"><span /> {patient?.status === 'inactive' ? 'Inactive patient' : 'Active patient'}</span></p>{patient?.existing_context_summary && <small className="patient-context-summary">{patient.existing_context_summary}</small>}</div></div><div className="patient-identifiers"><label>Patient ID<input aria-label="Patient ID" value={patientId} readOnly /></label></div></div>
}

function MemoryTabs({ view, onChange }: { view: MemoryView; onChange: (view: MemoryView) => void }) {
  const tabs: Array<{ id: Exclude<MemoryView, 'conflicts'>; label: string; icon: typeof HeartIcon }> = [
    { id: 'memory', label: 'Patient memory', icon: HeartIcon }, { id: 'timeline', label: 'Patient timeline', icon: ClockIcon }, { id: 'verified', label: 'Verified information', icon: CheckIcon }, { id: 'unverified', label: 'Unverified information', icon: AlertIcon },
  ]
  return <div className="memory-nav" role="tablist" aria-label="Patient memory views">{tabs.map(({ id, label, icon: Icon }) => <button key={id} role="tab" aria-selected={view === id} className={view === id ? 'active' : ''} onClick={() => onChange(id)}><Icon /> {label}</button>)}<Link className="memory-document-link" to="/documentation"><FileIcon /> Documentation <ArrowIcon /></Link></div>
}

function ClinicalQueryPanel({ query, setQuery, onSubmit, conversation, patient, patientId }: { query: string; setQuery: (value: string) => void; onSubmit: (value: string) => void; conversation: string[]; patient?: PatientRecord; patientId: string }) {
  const suggestions = ['Current medications', 'Recent medication changes', 'Allergy history', 'Recent hypertension history', 'Relevant procedures']
  return <SectionCard title="Ask about this patient's history" eyebrow="CLINICAL SEARCH" className="retrieval-card conversational-card"><form onSubmit={(event) => { event.preventDefault(); onSubmit(query) }}><div className="conversation-input-wrap"><SearchIcon /><input aria-label="Ask about this patient's history" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); onSubmit(query) } }} placeholder="What would you like to know about this patient's history?" /><button className="primary-button" type="submit"><SearchIcon /> Ask</button></div></form><div className="query-context"><span>{patient?.name ?? 'Patient record'} · Historical context loaded</span><span className="query-context-note">Patient <strong>{patientId}</strong></span></div><div className="suggested-questions"><span>Suggested questions</span>{suggestions.map((suggestion) => <button type="button" key={suggestion} onClick={() => onSubmit(suggestion)}>{suggestion}</button>)}</div>{conversation.length > 0 && <div className="conversation-history">{conversation.map((question, index) => <div className="conversation-turn" key={`${question}-${index}`}><span className="conversation-speaker physician">YOU</span><p>{question}</p></div>)}</div>}</SectionCard>
}

function MemoryWorkspace({ context, timeline, conflicts, question, hasSearched, isLoading, patientId, onFactClick, onApprove, onReject }: { context?: RetrievedContext; timeline: MemoryFact[]; conflicts: Conflict[]; question: string; hasSearched: boolean; isLoading: boolean; patientId: string; onFactClick: (fact: MemoryFact) => void; onApprove: (fact: MemoryFact) => void; onReject: (fact: MemoryFact) => void }) {
  return <><div className="memory-columns"><RelevantPatientContext context={context} question={question} hasSearched={hasSearched} isLoading={isLoading} onFactClick={onFactClick} onApprove={onApprove} onReject={onReject} /><RecentPatientActivity events={timeline} onFactClick={onFactClick} /></div><ConflictPreview conflicts={conflicts} patientId={patientId} onFactClick={onFactClick} /></>
}

type ContextItem = { fact: MemoryFact; verified: boolean }
function relevantItems(context: RetrievedContext, question: string): ContextItem[] {
  const items: ContextItem[] = [...contextCategories.flatMap((key) => context.verified_context[key].map((fact) => ({ fact, verified: true }))), ...context.unverified_information.map((fact) => ({ fact, verified: false }))]
  const terms = question.toLowerCase().split(/\s+/).filter((term) => term.length > 3 && !queryStopWords.has(term))
  const medicationQuery = /medication|medications|meds|drug|dose|prescription/.test(question.toLowerCase())
  const scored = items.map((item, index) => {
    const searchable = `${item.fact.normalized_concept} ${item.fact.entity_type} ${item.fact.clinical_domain} ${item.fact.assertion} ${item.fact.clinical_status}`.toLowerCase()
    const termScore = terms.reduce((score, term) => score + (searchable.includes(term) ? 4 : 0), 0)
    const categoryScore = medicationQuery && item.fact.entity_type.toLowerCase() === 'medication' ? 8 : 0
    return { item, score: termScore + categoryScore, index }
  })
  return scored.sort((a, b) => b.score - a.score || a.index - b.index).slice(0, medicationQuery ? 6 : 5).map(({ item }) => item)
}

function RelevantPatientContext({ context, question, hasSearched, isLoading, onFactClick, onApprove, onReject }: { context?: RetrievedContext; question: string; hasSearched: boolean; isLoading: boolean; onFactClick: (fact: MemoryFact) => void; onApprove: (fact: MemoryFact) => void; onReject: (fact: MemoryFact) => void }) {
  if (!hasSearched) return <SectionCard title="Relevant patient context" eyebrow="CURRENT QUERY" className="context-column-card"><div className="memory-empty-state"><SearchIcon /><p>Ask a question to see relevant patient context.</p></div></SectionCard>
  if (isLoading || !context) return <SectionCard title="Relevant patient context" eyebrow="CURRENT QUERY" className="context-column-card"><div className="empty-loading" aria-live="polite">Loading relevant patient context…</div></SectionCard>
  const items = relevantItems(context, question)
  const medicationItems = items.filter(({ fact }) => fact.entity_type.toLowerCase() === 'medication')
  const otherItems = items.filter(({ fact }) => fact.entity_type.toLowerCase() !== 'medication')
  return <SectionCard title="Relevant patient context" eyebrow="CURRENT QUERY" action={<span className="verified-heading"><CheckIcon /> Structured result</span>} className="context-column-card"><div className="assistant-response"><span className="assistant-avatar">M</span><div><p className="eyebrow">MEDFLOW</p><strong>Here is the relevant clinical context.</strong><span>Structured information is kept separated by verification status and safety priority.</span></div></div><div className="relevant-context-content">{medicationItems.length > 0 && <div className="relevant-group"><h3>Relevant medication history</h3><MedicationHistory facts={medicationItems.map(({ fact }) => fact)} onFactClick={onFactClick} /></div>}{otherItems.length > 0 && <div className="relevant-group"><h3>Relevant records</h3><div className="relevant-fact-list">{otherItems.map(({ fact, verified }) => <MemoryFactCard key={fact.event_id} fact={fact} onProvenance={onFactClick} onApprove={verified ? undefined : onApprove} onReject={verified ? undefined : onReject} />)}</div></div>}{medicationItems.length === 0 && otherItems.length === 0 && <p className="category-empty">No matching information was found in the structured patient context.</p>}</div></SectionCard>
}

function MedicationHistory({ facts, onFactClick }: { facts: MemoryFact[]; onFactClick: (fact: MemoryFact) => void }) {
  return <div className="medication-history-list">{facts.map((fact) => <button key={fact.event_id} className="medication-history-row" onClick={() => onFactClick(fact)}><div><span className="timeline-kicker">{fact.entity_type}</span><strong>{fact.normalized_concept}</strong><span>{fact.medication_attributes.dosage ?? 'Dose not recorded'}{fact.medication_attributes.frequency ? ` · ${fact.medication_attributes.frequency}` : ''}{fact.medication_attributes.route ? ` · ${fact.medication_attributes.route}` : ''}</span></div><div><TrustTierBadge tier={fact.trust_tier} /><small>{new Date(fact.event_timestamp).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</small><span className="medication-status">{fact.clinical_status}</span></div></button>)}</div>
}

function RecentPatientActivity({ events, onFactClick }: { events: MemoryFact[]; onFactClick: (fact: MemoryFact) => void }) {
  return <SectionCard title="Recent patient activity" eyebrow="QUICK REFERENCE" action={<span className="activity-count">{Math.min(events.length, 4)} recent events</span>} className="activity-column-card"><div className="activity-mini-list">{events.slice(0, 4).map((fact) => <button key={fact.event_id} onClick={() => onFactClick(fact)}><span className="activity-line" /><div><strong>{fact.normalized_concept}</strong><span>{fact.trust_tier === 3 ? 'Unverified information' : fact.trust_tier === 2 ? 'Physician-approved' : 'Verified record'} · {new Date(fact.event_timestamp).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</span></div><ArrowIcon /></button>)}</div></SectionCard>
}

function VerifiedInformationTab({ context, onFactClick }: { context?: RetrievedContext; onFactClick: (fact: MemoryFact) => void }) {
  if (!context) return <div className="empty-loading">Loading verified information…</div>
  const count = contextCategories.reduce((total, key) => total + context.verified_context[key].length, 0)
  return <SectionCard title="Verified information" eyebrow="VERIFIED PATIENT HISTORY" action={<span className="verified-heading"><CheckIcon /> {count} records</span>}><div className="memory-category-grid">{contextCategories.map((key) => <div className="memory-category" key={key}><div className="memory-category-title"><span>{categoryLabels[key]}</span><strong>{context.verified_context[key].length}</strong></div>{context.verified_context[key].length ? context.verified_context[key].map((fact) => <MemoryFactCard key={fact.event_id} fact={fact} onProvenance={onFactClick} />) : <p className="category-empty">No recorded information</p>}</div>)}</div></SectionCard>
}

function UnverifiedInformationTab({ context, onFactClick, onApprove, onReject }: { context?: RetrievedContext; onFactClick: (fact: MemoryFact) => void; onApprove: (fact: MemoryFact) => void; onReject: (fact: MemoryFact) => void }) {
  if (!context) return <div className="empty-loading">Loading unverified information…</div>
  return <SectionCard title="Unverified information" eyebrow="REVIEW BEFORE USE" action={<span className="unverified-heading"><AlertIcon /> {context.unverified_information.length} to review</span>}><div className="unverified-list">{context.unverified_information.map((fact) => <MemoryFactCard key={fact.event_id} fact={fact} onProvenance={onFactClick} onApprove={onApprove} onReject={onReject} />)}</div><div className="unverified-note"><AlertIcon /> Unverified information is never merged with verified patient history.</div></SectionCard>
}

function TimelineView({ events, onFactClick }: { events: MemoryFact[]; onFactClick: (fact: MemoryFact) => void }) {
  return <SectionCard title="Patient timeline" eyebrow="LONGITUDINAL PATIENT HISTORY" action={<span className="append-only-badge"><span className="append-dot" /> No records overwritten</span>}><div className="timeline-list">{events.map((event, index) => <div className="timeline-row" key={event.event_id}><div className="timeline-date"><strong>{new Date(event.event_timestamp).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</strong><span>{new Date(event.event_timestamp).getFullYear()}</span></div><div className="timeline-rail"><span className="timeline-node" />{index < events.length - 1 && <span className="timeline-connector" />}</div><button className="timeline-fact" onClick={() => onFactClick(event)}><div><span className="timeline-kicker">{event.entity_type} · {event.event_id}</span><strong>{event.normalized_concept}</strong><span>{event.medication_attributes.dosage ?? event.medication_attributes.route ?? event.assertion} · {event.clinical_status}</span></div><div className="timeline-right"><TrustTierBadge tier={event.trust_tier} /><span>{Math.round(event.extraction_confidence * 100)}% confidence</span><ArrowIcon /></div></button></div>)}</div><div className="timeline-invariant"><ClockIcon /><span><strong>History is preserved.</strong> Dose changes remain separate records: 500 mg → 1000 mg → discontinued.</span></div></SectionCard>
}

function ConflictPreview({ conflicts, patientId, onFactClick }: { conflicts: Conflict[]; patientId: string; onFactClick: (fact: MemoryFact) => void }) {
  if (conflicts.length === 0) return null
  const conflictHref = `/resolve-conflict?patient_id=${encodeURIComponent(patientId)}&conflict_id=${encodeURIComponent(conflicts[0].conflict_id)}`
  return <SectionCard title="Conflicting records" eyebrow="SAFETY REVIEW" action={<span className="high-risk-label"><AlertIcon /> {conflicts.length} conflicting record{conflicts.length === 1 ? '' : 's'}</span>} className="context-conflict-card"><div className="conflict-list">{conflicts.map((conflict) => <ConflictCard key={conflict.conflict_id} conflict={conflict} onResolve={() => undefined} onFactClick={onFactClick} compact />)}</div><Link className="conflict-review-link" to={conflictHref}>Review conflict <ArrowIcon /></Link></SectionCard>
}

function ConflictCenter({ conflicts, resolvedIds, onResolve, onFactClick }: { conflicts: Conflict[]; resolvedIds: string[]; onResolve: (id: string, action: 'confirm_event_a' | 'confirm_event_b' | 'keep_unresolved') => void; onFactClick: (fact: MemoryFact) => void }) {
  return <SectionCard title="Conflicting records" eyebrow="PHYSICIAN DECISION REQUIRED" action={<span className="high-risk-label"><AlertIcon /> Safety review</span>}><div className="conflict-list">{conflicts.map((conflict) => <ConflictCard key={conflict.conflict_id} conflict={conflict} resolved={resolvedIds.includes(conflict.conflict_id)} onResolve={(action) => onResolve(conflict.conflict_id, action)} onFactClick={onFactClick} />)}</div></SectionCard>
}

function ConflictCard({ conflict, resolved = false, onResolve, onFactClick, compact = false }: { conflict: Conflict; resolved?: boolean; onResolve: (action: 'confirm_event_a' | 'confirm_event_b' | 'keep_unresolved') => void; onFactClick: (fact: MemoryFact) => void; compact?: boolean }) {
  return <article className={`memory-conflict-card ${conflict.risk_level === 'high' ? 'high-risk-conflict' : ''} ${resolved ? 'resolved-conflict' : ''}`}><div className="conflict-header"><div><span className="conflict-kicker">{conflict.conflict_id} · {conflict.concept_thread}</span><h3>{conflict.risk_level === 'high' ? 'High safety priority' : `${conflict.risk_level} safety priority`}</h3></div><span className={`conflict-status ${resolved ? 'resolved' : conflict.status}`}>{resolved ? 'Decision recorded' : conflict.status === 'unresolved' ? 'Needs review' : conflict.status === 'dismissed' ? 'Reviewed — no resolution' : 'Resolved'}</span></div><div className="conflict-facts"><ConflictFact fact={conflict.event_a} label="Record 1" onClick={() => onFactClick(conflict.event_a)} /><div className="conflict-vs">VS</div><ConflictFact fact={conflict.event_b} label="Record 2" onClick={() => onFactClick(conflict.event_b)} /></div>{!compact && !resolved && <div className="conflict-actions"><button onClick={() => onResolve('confirm_event_a')}><CheckIcon /> Confirm record 1</button><button onClick={() => onResolve('confirm_event_b')}><CheckIcon /> Confirm record 2</button><button onClick={() => onResolve('keep_unresolved')}><XIcon /> Keep unresolved</button></div>}</article>
}

function ConflictFact({ fact, label, onClick }: { fact: MemoryFact; label: string; onClick: () => void }) {
  return <button className="conflict-fact" onClick={onClick}><span>{label} · {fact.trust_tier === 3 ? 'Unverified information' : fact.trust_tier === 2 ? 'Physician-approved' : 'Verified record'}</span><strong>{fact.normalized_concept}</strong><small>{fact.assertion} · {fact.clinical_status} · {fact.source_document_id}</small><TrustTierBadge tier={fact.trust_tier} /></button>
}

function applyTierActions(context: RetrievedContext | undefined, approvedIds: string[], rejectedIds: string[]): RetrievedContext | undefined {
  if (!context) return undefined
  const promoted = context.unverified_information.filter((fact) => approvedIds.includes(fact.event_id)).map((fact) => ({ ...fact, trust_tier: 2 as const, reviewed_status: 'not_applicable' as const, uiPromoted: true }))
  return { ...context, unverified_information: context.unverified_information.filter((fact) => !rejectedIds.includes(fact.event_id) && !approvedIds.includes(fact.event_id)), verified_context: { ...context.verified_context, medications: [...context.verified_context.medications, ...promoted] } }
}
