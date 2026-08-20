import { useEffect, useRef, useState } from 'react'
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
import { ActivityIcon, AlertIcon, ArrowIcon, CheckIcon, ClockIcon, FileIcon, HeartIcon, XIcon } from '../components/icons'

type MemoryView = 'memory' | 'timeline' | 'verified' | 'recent' | 'unverified' | 'conflicts'
type ConversationTurn = { id: number; question: string; response: RetrievedContext | null }

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
  const [conversation, setConversation] = useState<ConversationTurn[]>([])
  const nextTurnId = useRef(0)
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
  const activeContextConflicts = (context?.conflicts ?? conflicts).filter((conflict) => !isResolved(conflict.conflict_id))

  useEffect(() => {
    if (routeWorkflow && (routeWorkflow.patient_id !== workflow.patient_id || routeWorkflow.encounter_id !== workflow.encounter_id || routeWorkflow.document_id !== workflow.document_id)) setWorkflow(routeWorkflow)
    if (resolvedPatient && (resolvedPatient.patient_id !== workflow.patient_id || resolvedPatient.encounter_id !== workflow.encounter_id)) setWorkflow({ patient_id: resolvedPatient.patient_id, encounter_id: resolvedPatient.encounter_id })
  }, [location.state, resolvedPatient])

  useEffect(() => {
    if (!submittedQuestion || !context) return
    setConversation((turns) => {
      const lastTurn = turns[turns.length - 1]
      if (!lastTurn || lastTurn.question !== submittedQuestion || lastTurn.response === context) return turns
      return [...turns.slice(0, -1), { ...lastTurn, response: context }]
    })
  }, [context, submittedQuestion])

  const submitQuery = (question: string) => {
    const trimmed = question.trim()
    if (!trimmed) return
    setConversation((turns) => [...turns, { id: nextTurnId.current++, question: trimmed, response: null }])
    setSubmittedQuestion(trimmed)
    setSubmittedConcepts(deriveQueryConcepts(trimmed))
    setHasSearched(true)
    setQueryInput('')
  }
  const approveFact = (fact: MemoryFact) => { setApprovedIds((ids) => [...ids, fact.event_id]); approve.mutate({ eventId: fact.event_id, physicianId: 'phy_04' }) }
  const rejectFact = (fact: MemoryFact) => { setRejectedIds((ids) => [...ids, fact.event_id]); reject.mutate({ eventId: fact.event_id, physicianId: 'phy_04' }) }
  const resolveConflict = (conflictId: string, action: 'confirm_event_a' | 'confirm_event_b' | 'keep_unresolved') => { const conflict = conflicts.find((item) => item.conflict_id === conflictId); if (conflict) recordConflictResolution(conflict, action === 'confirm_event_a' ? 'keep_record_1' : action === 'confirm_event_b' ? 'keep_record_2' : 'mark_resolved'); setResolvedIds((ids) => [...ids, conflictId]); resolve.mutate({ conflictId, request: { resolution_action: action, physician_id: 'phy_04' } }) }

  return <div className="page-stack memory-page">
    <PatientMemoryHeader patient={resolvedPatient} patientId={patientId} />
    <MemoryTabs view={view} onChange={setView} />
    {view === 'memory' && <><MemoryChatWorkspace conversation={conversation} context={displayedContext} hasSearched={hasSearched} isLoading={isLoading || patientRecord.isLoading} query={queryInput} setQuery={setQueryInput} onSubmit={submitQuery} patient={resolvedPatient} patientId={patientId} approvedIds={approvedIds} rejectedIds={rejectedIds} onFactClick={setSelectedFact} onApprove={approveFact} onReject={rejectFact} onViewTimeline={() => setView('timeline')} onViewRecent={() => setView('recent')} timeline={timeline} /><ConflictPreview conflicts={activeContextConflicts} patientId={patientId} onFactClick={setSelectedFact} /></>}
    {view === 'timeline' && <TimelineView events={timeline} onFactClick={setSelectedFact} />}
    {view === 'verified' && <VerifiedInformationTab context={displayedContext} onFactClick={setSelectedFact} />}
    {view === 'recent' && <RecentActivityView events={timeline} onFactClick={setSelectedFact} />}
    {view === 'unverified' && <UnverifiedInformationTab context={displayedContext} onFactClick={setSelectedFact} onApprove={approveFact} onReject={rejectFact} />}
    {view === 'conflicts' && <><div className="conflict-route-header"><Link className="memory-context-back" to={'/memory?patient_id=' + encodeURIComponent(patientId)}><ArrowIcon /> Back to patient memory</Link></div><ConflictCenter conflicts={conflicts} resolvedIds={resolvedIds} onResolve={resolveConflict} onFactClick={setSelectedFact} /></>}
    {selectedFact && <MemoryProvenanceDrawer fact={selectedFact} onClose={() => setSelectedFact(null)} />}
  </div>
}

function PatientMemoryHeader({ patient, patientId }: { patient?: PatientRecord; patientId: string }) {
  const name = patient?.name ?? 'Patient record'
  const initials = name === 'Patient record' ? 'P' : name.split(' ').map((part) => part[0]).join('').slice(0, 2)
  return <header className="memory-compact-header"><div className="memory-compact-profile"><div className="memory-compact-avatar">{initials}</div><div><p className="eyebrow">PATIENT MEMORY</p><h1>{name}</h1><p className="memory-compact-meta">{patient ? patient.age + ' years - ' + patient.gender + ' - ' : ''}<span className="memory-compact-status"><span /> {patient?.status === 'inactive' ? 'Inactive' : 'Active'}</span></p></div></div><div className="memory-compact-id"><span>ID</span><input aria-label="Patient ID" value={patientId} readOnly /></div></header>
}

function MemoryTabs({ view, onChange }: { view: MemoryView; onChange: (view: MemoryView) => void }) {
  const tabs: Array<{ id: 'memory' | 'timeline' | 'verified' | 'unverified'; label: string; icon: typeof HeartIcon }> = [
    { id: 'memory', label: 'Patient memory', icon: HeartIcon }, { id: 'timeline', label: 'Patient timeline', icon: ClockIcon }, { id: 'verified', label: 'Verified information', icon: CheckIcon }, { id: 'unverified', label: 'Unverified information', icon: AlertIcon },
  ]
  return <div className="memory-nav"><div className="memory-tablist" role="tablist" aria-label="Patient memory views">{tabs.map(({ id, label, icon: Icon }) => <button key={id} role="tab" aria-selected={view === id} className={view === id ? 'active' : ''} onClick={() => onChange(id)}><Icon /> {label}</button>)}</div><button type="button" className={'memory-secondary-tab ' + (view === 'recent' ? 'active' : '')} aria-pressed={view === 'recent'} onClick={() => onChange('recent')}><ActivityIcon /> Recent Activity</button><Link className="memory-document-link" to="/documentation"><FileIcon /> Documentation <ArrowIcon /></Link></div>
}

function MemoryChatWorkspace({ conversation, context, hasSearched, isLoading, query, setQuery, onSubmit, patient, patientId, approvedIds, rejectedIds, onFactClick, onApprove, onReject, onViewTimeline, onViewRecent, timeline }: { conversation: ConversationTurn[]; context?: RetrievedContext; hasSearched: boolean; isLoading: boolean; query: string; setQuery: (value: string) => void; onSubmit: (value: string) => void; patient?: PatientRecord; patientId: string; approvedIds: string[]; rejectedIds: string[]; onFactClick: (fact: MemoryFact) => void; onApprove: (fact: MemoryFact) => void; onReject: (fact: MemoryFact) => void; onViewTimeline: () => void; onViewRecent: () => void; timeline: MemoryFact[] }) {
  const conversationRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (conversationRef.current) conversationRef.current.scrollTop = conversationRef.current.scrollHeight
  }, [conversation.length, isLoading])

  return <div className="memory-ai-workspace">
    <section className="memory-chat-panel" aria-label="Patient memory assistant">
      <div className="memory-chat-heading"><div><p className="eyebrow">CLINICAL MEMORY ASSISTANT</p><h2>Ask about this patient</h2><span className="memory-chat-context-label">Relevant patient context</span><span>Conversation stays linked to source records and verification state.</span></div><span className="memory-grounded-pill"><span /> Source-grounded</span></div>
      <div className="memory-chat-scroll" ref={conversationRef} role="log" aria-live="polite">
        <MemoryConversation conversation={conversation} context={context} hasSearched={hasSearched} isLoading={isLoading} approvedIds={approvedIds} rejectedIds={rejectedIds} onFactClick={onFactClick} onApprove={onApprove} onReject={onReject} />
      </div>
      <MemoryComposer query={query} setQuery={setQuery} onSubmit={onSubmit} patient={patient} patientId={patientId} />
    </section>
    <MemoryContextRail context={context} timeline={timeline} onFactClick={onFactClick} onViewTimeline={onViewTimeline} onViewRecent={onViewRecent} />
  </div>
}

function MemoryConversation({ conversation, context, hasSearched, isLoading, approvedIds, rejectedIds, onFactClick, onApprove, onReject }: { conversation: ConversationTurn[]; context?: RetrievedContext; hasSearched: boolean; isLoading: boolean; approvedIds: string[]; rejectedIds: string[]; onFactClick: (fact: MemoryFact) => void; onApprove: (fact: MemoryFact) => void; onReject: (fact: MemoryFact) => void }) {
  return <div className="memory-conversation">
    {conversation.length === 0 && <div className="memory-ai-intro"><div className="memory-message-avatar">M</div><div><div className="memory-message-label"><strong>MedFlow AI</strong><span>Patient memory</span></div><p>{hasSearched && context ? 'Patient context is loaded. Ask a question to explore the record.' : 'Ask a question to explore this patient record.'}</p><span className="memory-ai-note">Every surfaced record keeps its source and verification level visible.</span></div></div>}
    {conversation.map((turn, index) => {
      const responseContext = turn.response ? applyTierActions(turn.response, approvedIds, rejectedIds) : index === conversation.length - 1 && !isLoading ? context : undefined
      return <div className="memory-conversation-turn" key={turn.id}><div className="memory-user-message"><span className="memory-message-avatar memory-user-avatar">You</span><p>{turn.question}</p></div><MemoryAssistantMessage context={responseContext} question={turn.question} isLoading={index === conversation.length - 1 && isLoading && !turn.response} onFactClick={onFactClick} onApprove={onApprove} onReject={onReject} /></div>
    })}
  </div>
}

function MemoryAssistantMessage({ context, question, isLoading, onFactClick, onApprove, onReject }: { context?: RetrievedContext; question: string; isLoading: boolean; onFactClick: (fact: MemoryFact) => void; onApprove: (fact: MemoryFact) => void; onReject: (fact: MemoryFact) => void }) {
  const items = context ? relevantItems(context, question) : []
  const medicationItems = items.filter(({ fact }) => fact.entity_type.toLowerCase() === 'medication')
  return <div className="memory-ai-message"><div className="memory-message-avatar">M</div><div className="memory-ai-message-body"><div className="memory-message-label"><strong>MedFlow AI</strong><span>Clinical memory</span></div>{isLoading ? <div className="memory-thinking" aria-live="polite"><span /><span /><span /> Searching sourced records</div> : context ? <><p>Here is the relevant clinical context.</p>{medicationItems.length > 0 && <h3 className="memory-response-heading">Relevant medication history</h3>}{items.length > 0 ? <div className="memory-response-facts">{items.map((item) => <MemoryResponseFact key={item.fact.event_id} item={item} onApprove={onApprove} onReject={onReject} />)}</div> : <p className="memory-response-empty">No matching information was found in the structured patient context.</p>}<MemoryResponseSources facts={items.map((item) => item.fact)} onFactClick={onFactClick} /></> : <p className="memory-response-empty">The patient context is still loading.</p>}</div></div>
}

function MemoryResponseFact({ item, onApprove, onReject }: { item: ContextItem; onApprove: (fact: MemoryFact) => void; onReject: (fact: MemoryFact) => void }) {
  const fact = item.fact
  return <article className={'memory-response-fact ' + (item.verified ? 'verified' : 'unverified')}><div className="memory-response-fact-copy"><span className="memory-response-kicker">{fact.entity_type}</span><strong>{fact.normalized_concept}</strong><span>{formatFactDetail(fact)}</span></div><TrustTierBadge tier={fact.trust_tier} />{!item.verified && fact.trust_tier === 3 && <div className="memory-response-actions"><button type="button" className="memory-response-approve" onClick={() => onApprove(fact)}><CheckIcon /> Approve</button><button type="button" className="memory-response-reject" onClick={() => onReject(fact)}><XIcon /> Reject</button></div>}</article>
}

function MemoryResponseSources({ facts, onFactClick }: { facts: MemoryFact[]; onFactClick: (fact: MemoryFact) => void }) {
  const sources = [...new Map(facts.map((fact) => [fact.source_document_id, fact])).values()].slice(0, 3)
  if (sources.length === 0) return null
  return <div className="memory-response-sources"><span className="memory-sources-label">Sources</span><div>{sources.map((fact) => <button type="button" className="memory-source-chip" key={fact.source_document_id} onClick={() => onFactClick(fact)} aria-label={'Open source ' + fact.source_document_id}><FileIcon /><span>{fact.source_document_id}</span><small>{formatMemoryDate(fact.event_timestamp)}</small></button>)}</div></div>
}

function MemoryComposer({ query, setQuery, onSubmit, patient, patientId }: { query: string; setQuery: (value: string) => void; onSubmit: (value: string) => void; patient?: PatientRecord; patientId: string }) {
  const suggestions = ['Current medications', 'Recent medication changes', 'Allergy history', 'Recent hypertension history', 'Relevant procedures']
  return <div className="memory-composer-wrap"><form className="memory-composer" onSubmit={(event) => { event.preventDefault(); onSubmit(query) }}><textarea aria-label="Ask about this patient's history" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); onSubmit(query) } }} placeholder="Ask about this patient's medical history..." rows={1} /><button className="memory-composer-submit" type="submit" aria-label="Ask"><ArrowIcon /></button></form><div className="memory-composer-footer"><span>{patient?.name ?? 'Patient record'} - {patientId}</span><span>Shift + Enter for a new line</span></div><div className="memory-prompt-row"><span>Try asking</span>{suggestions.map((suggestion) => <button type="button" key={suggestion} onClick={() => onSubmit(suggestion)}>{suggestion}</button>)}</div></div>
}

function MemoryContextRail({ context, timeline, onFactClick, onViewTimeline, onViewRecent }: { context?: RetrievedContext; timeline: MemoryFact[]; onFactClick: (fact: MemoryFact) => void; onViewTimeline: () => void; onViewRecent: () => void }) {
  const medications = context?.verified_context.medications.filter((fact) => fact.clinical_status === 'active' && fact.temporal_context === 'current') ?? []
  const events = recentClinicalEvents(context, timeline)
  return <aside className="memory-context-rail" aria-label="Patient clinical context"><div className="memory-rail-heading"><div><p className="eyebrow">PATIENT CONTEXT</p><h2>Keep in view</h2></div><span className="memory-rail-live"><span /> Live memory</span></div><section className="memory-rail-section"><div className="memory-rail-section-heading"><div><span className="memory-rail-kicker">CURRENT MEDICATIONS</span><strong>{medications.length} active</strong></div><HeartIcon /></div>{context && medications.length > 0 ? <div className="memory-current-medications">{medications.slice(0, 3).map((fact) => <button type="button" key={fact.event_id} onClick={() => onFactClick(fact)}><span className="memory-medication-name">{fact.normalized_concept}</span><span>{formatMedicationDetail(fact)} - Active</span></button>)}</div> : context ? <p className="memory-rail-empty">No active medications in verified context.</p> : <p className="memory-rail-loading">Loading patient context...</p>}{medications.length > 3 && <button type="button" className="memory-rail-view-all" onClick={onViewTimeline}>View all medication records <ArrowIcon /></button>}</section><section className="memory-rail-section"><div className="memory-rail-section-heading"><div><span className="memory-rail-kicker">RECENT EVENTS</span><strong>{events.length} clinical records</strong></div><ActivityIcon /></div>{events.length > 0 ? <div className="memory-recent-events">{events.map((fact) => <RecentEventRow key={fact.event_id} fact={fact} onFactClick={onFactClick} compact />)}</div> : context ? <p className="memory-rail-empty">No recent clinical events.</p> : <p className="memory-rail-loading">Loading recent events...</p>}<button type="button" className="memory-rail-view-all" onClick={onViewTimeline}>View full timeline <ArrowIcon /></button><button type="button" className="memory-rail-view-all" onClick={onViewRecent}>Recent patient activity <ArrowIcon /></button></section></aside>
}

type ContextItem = { fact: MemoryFact; verified: boolean }

function relevantItems(context: RetrievedContext, question: string): ContextItem[] {
  const items: ContextItem[] = [...contextCategories.flatMap((key) => context.verified_context[key].map((fact) => ({ fact, verified: true }))), ...context.unverified_information.map((fact) => ({ fact, verified: false }))]
  const terms = question.toLowerCase().split(/\s+/).filter((term) => term.length > 3 && !queryStopWords.has(term))
  const medicationQuery = /medication|medications|meds|drug|dose|prescription/.test(question.toLowerCase())
  const scored = items.map((item, index) => {
    const searchable = (item.fact.normalized_concept + ' ' + item.fact.entity_type + ' ' + item.fact.clinical_domain + ' ' + item.fact.assertion + ' ' + item.fact.clinical_status).toLowerCase()
    const termScore = terms.reduce((score, term) => score + (searchable.includes(term) ? 4 : 0), 0)
    const categoryScore = medicationQuery && item.fact.entity_type.toLowerCase() === 'medication' ? 8 : 0
    return { item, score: termScore + categoryScore, index }
  })
  return scored.sort((a, b) => b.score - a.score || a.index - b.index).slice(0, medicationQuery ? 6 : 5).map(({ item }) => item)
}

function recentClinicalEvents(context: RetrievedContext | undefined, timeline: MemoryFact[]): MemoryFact[] {
  const contextEvents = context ? [
    ...context.verified_context.conditions,
    ...context.verified_context.allergies,
    ...context.verified_context.procedures,
    ...context.verified_context.lab_trends,
    ...context.verified_context.significant_events,
    ...context.unverified_information,
  ] : []
  const unique = new Map<string, MemoryFact>()
  for (const fact of [...contextEvents, ...timeline]) unique.set(fact.event_id, fact)
  return [...unique.values()].sort((a, b) => new Date(b.event_timestamp).getTime() - new Date(a.event_timestamp).getTime()).slice(0, 4)
}

function RecentEventRow({ fact, onFactClick, compact = false }: { fact: MemoryFact; onFactClick: (fact: MemoryFact) => void; compact?: boolean }) {
  return <button type="button" className={'memory-event-row ' + (compact ? 'compact' : '')} onClick={() => onFactClick(fact)}><span className="memory-event-icon"><MemoryEventIcon fact={fact} /></span><span className="memory-event-copy"><strong>{formatEventLabel(fact)}</strong><small>{formatFactDetail(fact)}</small></span><span className="memory-event-date">{formatMemoryDate(fact.event_timestamp)}</span><ArrowIcon /></button>
}

function MemoryEventIcon({ fact }: { fact: MemoryFact }) {
  const type = fact.entity_type.toLowerCase()
  if (type.includes('lab')) return <FileIcon />
  if (type.includes('allergy')) return <AlertIcon />
  if (type.includes('medication') || type.includes('dosage')) return <HeartIcon />
  return <ActivityIcon />
}

function formatEventLabel(fact: MemoryFact): string {
  if (fact.entity_type.toLowerCase().includes('medication') && fact.medication_attributes.route === 'discontinued') return fact.normalized_concept + ' discontinued'
  return fact.normalized_concept
}

function formatMedicationDetail(fact: MemoryFact): string {
  return [fact.medication_attributes.dosage, fact.medication_attributes.frequency, fact.medication_attributes.route].filter(Boolean).join(' - ')
}

function formatFactDetail(fact: MemoryFact): string {
  const medicationDetail = formatMedicationDetail(fact)
  if (medicationDetail) return medicationDetail + ' - ' + fact.clinical_status
  if (fact.lab_attributes && (fact.lab_attributes.test_name || fact.lab_attributes.value)) return [fact.lab_attributes.test_name, fact.lab_attributes.value, fact.lab_attributes.unit].filter(Boolean).join(' ') + ' - ' + fact.clinical_status
  return fact.assertion + ' - ' + fact.clinical_status + ' - ' + fact.temporal_context
}

function formatMemoryDate(value: string): string {
  return new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function RecentActivityView({ events, onFactClick }: { events: MemoryFact[]; onFactClick: (fact: MemoryFact) => void }) {
  return <SectionCard title="Recent Activity" eyebrow="MEMORY ACTIVITY" action={<span className="activity-count">{events.length} recorded events</span>}><p className="memory-activity-intro">Recent memory events currently returned for this patient. Select an event to inspect its source and verification trail.</p><div className="memory-activity-feed">{events.map((fact) => <RecentEventRow key={fact.event_id} fact={fact} onFactClick={onFactClick} />)}</div></SectionCard>
}

function VerifiedInformationTab({ context, onFactClick }: { context?: RetrievedContext; onFactClick: (fact: MemoryFact) => void }) {
  if (!context) return <div className="empty-loading">Loading verified information...</div>
  const count = contextCategories.reduce((total, key) => total + context.verified_context[key].length, 0)
  return <SectionCard title="Verified information" eyebrow="VERIFIED PATIENT HISTORY" action={<span className="verified-heading"><CheckIcon /> {count} records</span>}><div className="memory-category-grid">{contextCategories.map((key) => <div className="memory-category" key={key}><div className="memory-category-title"><span>{categoryLabels[key]}</span><strong>{context.verified_context[key].length}</strong></div>{context.verified_context[key].length ? context.verified_context[key].map((fact) => <MemoryFactCard key={fact.event_id} fact={fact} onProvenance={onFactClick} />) : <p className="category-empty">No recorded information</p>}</div>)}</div></SectionCard>
}

function UnverifiedInformationTab({ context, onFactClick, onApprove, onReject }: { context?: RetrievedContext; onFactClick: (fact: MemoryFact) => void; onApprove: (fact: MemoryFact) => void; onReject: (fact: MemoryFact) => void }) {
  if (!context) return <div className="empty-loading">Loading unverified information...</div>
  return <SectionCard title="Unverified information" eyebrow="REVIEW BEFORE USE" action={<span className="unverified-heading"><AlertIcon /> {context.unverified_information.length} to review</span>}><div className="unverified-list">{context.unverified_information.map((fact) => <MemoryFactCard key={fact.event_id} fact={fact} onProvenance={onFactClick} onApprove={onApprove} onReject={onReject} />)}</div><div className="unverified-note"><AlertIcon /> Unverified information is never merged with verified patient history.</div></SectionCard>
}

function TimelineView({ events, onFactClick }: { events: MemoryFact[]; onFactClick: (fact: MemoryFact) => void }) {
  return <SectionCard title="Patient timeline" eyebrow="LONGITUDINAL PATIENT HISTORY" action={<span className="append-only-badge"><span className="append-dot" /> No records overwritten</span>}><div className="timeline-list">{events.map((event, index) => <div className="timeline-row" key={event.event_id}><div className="timeline-date"><strong>{new Date(event.event_timestamp).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</strong><span>{new Date(event.event_timestamp).getFullYear()}</span></div><div className="timeline-rail"><span className="timeline-node" />{index < events.length - 1 && <span className="timeline-connector" />}</div><button className="timeline-fact" onClick={() => onFactClick(event)}><div><span className="timeline-kicker">{event.entity_type} - {event.event_id}</span><strong>{event.normalized_concept}</strong><span>{event.medication_attributes.dosage ?? event.medication_attributes.route ?? event.assertion} - {event.clinical_status}</span></div><div className="timeline-right"><TrustTierBadge tier={event.trust_tier} /><span>{Math.round(event.extraction_confidence * 100)}% confidence</span><ArrowIcon /></div></button></div>)}</div><div className="timeline-invariant"><ClockIcon /><span><strong>History is preserved.</strong> Dose changes remain separate records: 500 mg - 1000 mg - discontinued.</span></div></SectionCard>
}

function ConflictPreview({ conflicts, patientId, onFactClick }: { conflicts: Conflict[]; patientId: string; onFactClick: (fact: MemoryFact) => void }) {
  if (conflicts.length === 0) return null
  const conflictHref = '/resolve-conflict?patient_id=' + encodeURIComponent(patientId) + '&conflict_id=' + encodeURIComponent(conflicts[0].conflict_id)
  return <SectionCard title="Conflicting records" eyebrow="SAFETY REVIEW" action={<span className="high-risk-label"><AlertIcon /> {conflicts.length} conflicting record{conflicts.length === 1 ? '' : 's'}</span>} className="context-conflict-card"><div className="conflict-list">{conflicts.map((conflict) => <ConflictCard key={conflict.conflict_id} conflict={conflict} onResolve={() => undefined} onFactClick={onFactClick} compact />)}</div><Link className="conflict-review-link" to={conflictHref}>Review conflict <ArrowIcon /></Link></SectionCard>
}

function ConflictCenter({ conflicts, resolvedIds, onResolve, onFactClick }: { conflicts: Conflict[]; resolvedIds: string[]; onResolve: (id: string, action: 'confirm_event_a' | 'confirm_event_b' | 'keep_unresolved') => void; onFactClick: (fact: MemoryFact) => void }) {
  return <SectionCard title="Conflicting records" eyebrow="PHYSICIAN DECISION REQUIRED" action={<span className="high-risk-label"><AlertIcon /> Safety review</span>}><div className="conflict-list">{conflicts.map((conflict) => <ConflictCard key={conflict.conflict_id} conflict={conflict} resolved={resolvedIds.includes(conflict.conflict_id)} onResolve={(action) => onResolve(conflict.conflict_id, action)} onFactClick={onFactClick} />)}</div></SectionCard>
}

function ConflictCard({ conflict, resolved = false, onResolve, onFactClick, compact = false }: { conflict: Conflict; resolved?: boolean; onResolve: (action: 'confirm_event_a' | 'confirm_event_b' | 'keep_unresolved') => void; onFactClick: (fact: MemoryFact) => void; compact?: boolean }) {
  return <article className={'memory-conflict-card ' + (conflict.risk_level === 'high' ? 'high-risk-conflict' : '') + (resolved ? ' resolved-conflict' : '')}><div className="conflict-header"><div><span className="conflict-kicker">{conflict.conflict_id} - {conflict.concept_thread}</span><h3>{conflict.risk_level === 'high' ? 'High safety priority' : conflict.risk_level + ' safety priority'}</h3></div><span className={'conflict-status ' + (resolved ? 'resolved' : conflict.status)}>{resolved ? 'Decision recorded' : conflict.status === 'unresolved' ? 'Needs review' : conflict.status === 'dismissed' ? 'Reviewed - no resolution' : 'Resolved'}</span></div><div className="conflict-facts"><ConflictFact fact={conflict.event_a} label="Record 1" onClick={() => onFactClick(conflict.event_a)} /><div className="conflict-vs">VS</div><ConflictFact fact={conflict.event_b} label="Record 2" onClick={() => onFactClick(conflict.event_b)} /></div>{!compact && !resolved && <div className="conflict-actions"><button onClick={() => onResolve('confirm_event_a')}><CheckIcon /> Confirm record 1</button><button onClick={() => onResolve('confirm_event_b')}><CheckIcon /> Confirm record 2</button><button onClick={() => onResolve('keep_unresolved')}><XIcon /> Keep unresolved</button></div>}</article>
}

function ConflictFact({ fact, label, onClick }: { fact: MemoryFact; label: string; onClick: () => void }) {
  return <button className="conflict-fact" onClick={onClick}><span>{label} - {fact.trust_tier === 3 ? 'Unverified information' : fact.trust_tier === 2 ? 'Physician-approved' : 'Verified record'}</span><strong>{fact.normalized_concept}</strong><small>{fact.assertion} - {fact.clinical_status} - {fact.source_document_id}</small><TrustTierBadge tier={fact.trust_tier} /></button>
}

function applyTierActions(context: RetrievedContext | undefined, approvedIds: string[], rejectedIds: string[]): RetrievedContext | undefined {
  if (!context) return undefined
  const promoted = context.unverified_information.filter((fact) => approvedIds.includes(fact.event_id)).map((fact) => ({ ...fact, trust_tier: 2 as const, reviewed_status: 'not_applicable' as const, uiPromoted: true }))
  return { ...context, unverified_information: context.unverified_information.filter((fact) => !rejectedIds.includes(fact.event_id) && !approvedIds.includes(fact.event_id)), verified_context: { ...context.verified_context, medications: [...context.verified_context.medications, ...promoted] } }
}
