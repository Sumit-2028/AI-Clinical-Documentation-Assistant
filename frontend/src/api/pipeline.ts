import type { ClinicalEvent, Step2Response } from '../contracts/clinicalEvent'
import type { DocumentGenerationRequest, DocumentHistoryItem, FinalizationRequest, FinalizationResponse, GeneratedDocument } from '../contracts/documents'
import type { ConflictResolutionRequest, ConflictResolutionResponse, MemoryFact, MemoryRetrieveRequest, MemoryWriteRequest, MemoryWriteResponse, Tier3ApprovalResponse, Tier3RejectionResponse } from '../contracts/memory'
import type { RetrievedContext } from '../contracts/retrievedContext'
import type { Step1Output } from '../contracts/step1Output'
import { apiClient } from './client'
import clinicalEvents from '../mocks/clinical-events.json'
import memoryWriteResponse from '../mocks/memory-write-response.json'
import retrievedContext from '../mocks/retrieved-context.json'
import soapDocument from '../mocks/soap-document.json'
import dischargeDocument from '../mocks/discharge-document.json'
import memoryEvents from '../mocks/memory-events.json'

const resolved = <T,>(value: T): Promise<T> => Promise.resolve(value)
const clinicalEventFixture = clinicalEvents as unknown as Step2Response
const memoryWriteFixture = memoryWriteResponse as unknown as MemoryWriteResponse
const retrievedContextFixture = retrievedContext as unknown as RetrievedContext
const soapDocumentFixture = soapDocument as unknown as GeneratedDocument
const dischargeDocumentFixture = dischargeDocument as unknown as GeneratedDocument
const memoryEventsFixture = memoryEvents as unknown as MemoryFact[]
const physicianApprovedEvents = clinicalEventFixture.clinical_events.filter((event) => event.validation_status === 'valid')
const documentFixtures: GeneratedDocument[] = [soapDocumentFixture, dischargeDocumentFixture]
let documentHistory: DocumentHistoryItem[] = documentFixtures.map((document) => ({ ...document, finalized_at: null }))
const useFixtures = import.meta.env.MODE === 'test'

interface BackendProvenance {
  source_document_id: string
  source_event_id: string
  source_text_span: { start: number; end: number }
  input_modality: string
  source_language: string
  confidence: number
  captured_at: string
  physician_approval?: Record<string, unknown> | null
}

interface BackendMemoryItem {
  event_id: string
  concept_thread_id: string
  normalized_concept: string
  clinical_status: string
  assertion: string
  temporal_context: string
  original_text: string
  trust_tier: 1 | 2 | 3
  provenance: BackendProvenance
}

interface BackendMemoryEvent extends BackendMemoryItem {
  patient_id: string
  encounter_id: string
  source_event_id: string
  processed_text: string
  snomed_ct_id: string | null
  entity_type: string
  clinical_domain: string
  temporal_date: string | null
  reviewed_status: string
  created_at: string
  current_trust_tier: 1 | 2 | 3
}

interface BackendConflict {
  conflict_id: string
  patient_id: string
  concept_thread_id: string
  event_a_id: string
  event_b_id: string
  conflict_type: string
  risk_level: string
  status: 'unresolved' | 'resolved'
}

interface BackendRetrievedContext {
  verified_context: Record<'conditions' | 'medications' | 'allergies' | 'procedures' | 'lab_trends' | 'significant_events', BackendMemoryItem[]>
  unverified_information: BackendMemoryItem[]
  conflicts: BackendConflict[]
}

function toMemoryFact(item: BackendMemoryItem | BackendMemoryEvent): MemoryFact {
  const provenance = item.provenance
  return {
    event_id: item.event_id,
    concept_thread_id: item.concept_thread_id,
    normalized_concept: item.normalized_concept,
    snomed_ct_id: 'snomed_ct_id' in item ? item.snomed_ct_id : null,
    entity_type: 'entity_type' in item ? item.entity_type : 'Clinical finding',
    clinical_domain: 'clinical_domain' in item ? item.clinical_domain : 'not provided',
    assertion: item.assertion as MemoryFact['assertion'],
    clinical_status: item.clinical_status as MemoryFact['clinical_status'],
    temporal_context: item.temporal_context,
    trust_tier: item.trust_tier,
    reviewed_status: 'reviewed_status' in item
      ? item.reviewed_status as MemoryFact['reviewed_status']
      : item.trust_tier === 3 ? 'never_reviewed' : 'not_applicable',
    thread_match_confidence: 'unknown',
    source_document_id: provenance.source_document_id,
    source_text_span: provenance.source_text_span,
    input_modality: provenance.input_modality as MemoryFact['input_modality'],
    source_language: provenance.source_language,
    translation_confidence: null,
    extraction_confidence: provenance.confidence,
    contextualization_confidence: provenance.confidence,
    event_timestamp: 'created_at' in item ? item.created_at : provenance.captured_at,
    ingestion_timestamp: provenance.captured_at,
    medication_attributes: { dosage: null, frequency: null, route: null },
    provenance: provenance as unknown as Record<string, unknown>,
  }
}

function toConflict(record: BackendConflict, facts: MemoryFact[]): RetrievedContext['conflicts'][number] {
  return {
    conflict_id: record.conflict_id,
    concept_thread: record.concept_thread_id,
    risk_level: record.risk_level as RetrievedContext['conflicts'][number]['risk_level'],
    status: record.status,
    event_a_id: record.event_a_id,
    event_b_id: record.event_b_id,
    conflict_type: record.conflict_type,
    event_a: facts.find((fact) => fact.event_id === record.event_a_id),
    event_b: facts.find((fact) => fact.event_id === record.event_b_id),
  }
}

function toRetrievedContext(response: BackendRetrievedContext, facts: MemoryFact[] = []): RetrievedContext {
  const categories = ['conditions', 'medications', 'allergies', 'procedures', 'lab_trends', 'significant_events'] as const
  return {
    verified_context: Object.fromEntries(categories.map((category) => [category, response.verified_context[category].map(toMemoryFact)])) as RetrievedContext['verified_context'],
    unverified_information: response.unverified_information.map(toMemoryFact),
    conflicts: response.conflicts.map((conflict) => toConflict(conflict, facts)),
  }
}

function backendEventPayload(event: ClinicalEvent): Record<string, unknown> {
  const { ambiguous_abbreviation_resolved: _abbreviation, medication_attributes: _medication, lab_attributes: _lab, ...backendEvent } = event
  return backendEvent as unknown as Record<string, unknown>
}

function backendContextItem(fact: MemoryFact): Record<string, unknown> {
  const provenance = fact.provenance ?? {
    source_document_id: fact.source_document_id,
    source_event_id: fact.event_id,
    source_text_span: fact.source_text_span,
    input_modality: fact.input_modality,
    source_language: fact.source_language,
    confidence: fact.extraction_confidence,
    captured_at: fact.ingestion_timestamp,
    physician_approval: null,
  }
  return {
    event_id: fact.event_id,
    concept_thread_id: fact.concept_thread_id,
    normalized_concept: fact.normalized_concept,
    clinical_status: fact.clinical_status,
    assertion: fact.assertion,
    temporal_context: fact.temporal_context,
    original_text: fact.normalized_concept,
    trust_tier: fact.trust_tier,
    provenance,
  }
}

function backendRetrievedContext(context: RetrievedContext): Record<string, unknown> {
  const categories = ['conditions', 'medications', 'allergies', 'procedures', 'lab_trends', 'significant_events'] as const
  return {
    verified_context: Object.fromEntries(categories.map((category) => [category, context.verified_context[category].map(backendContextItem)])),
    unverified_information: context.unverified_information.map(backendContextItem),
    conflicts: context.conflicts.map((conflict) => ({
      conflict_id: conflict.conflict_id,
      concept_thread_id: conflict.concept_thread,
      event_a_id: conflict.event_a_id ?? conflict.event_a?.event_id,
      event_b_id: conflict.event_b_id ?? conflict.event_b?.event_id,
      conflict_type: conflict.conflict_type ?? 'unresolved_conflict',
      risk_level: conflict.risk_level,
      status: conflict.status === 'dismissed' ? 'resolved' : conflict.status,
    })),
  }
}

interface BackendGeneratedDocument {
  document_id: string
  patient_id: string
  encounter_id: string
  document_type: 'soap_note' | 'discharge_summary'
  status: 'draft' | 'finalized'
  sections: GeneratedDocument['sections']
  flags_for_physician_review: Array<{ code: string; message: string; severity: string; section?: string | null; source_event_ids: string[] }>
  provenance_map: Array<{ section: string; generated_text: string; source_event_ids: string[]; source_document_ids: string[]; source_kind: string; trust_tier: 1 | 2 | 3 | null; confidence: number; is_inferred: boolean }>
  validation_result: { passed: boolean; failures: Array<{ code: string; message: string; section?: string | null }>; auto_regeneration_attempts: number }
  generated_at: string
  finalized_at?: string | null
  generator?: string
}

function normalizeGeneratedDocument(raw: BackendGeneratedDocument): GeneratedDocument {
  const provenance = raw.provenance_map.map((entry, index) => ({
    fact_id: entry.source_event_ids[0] ?? `${raw.document_id}-${entry.section}-${index}`,
    trust_tier: entry.trust_tier ?? 'current_encounter' as const,
    source_document_id: entry.source_document_ids[0] ?? null,
    original_text: entry.generated_text,
    source_language: 'unknown',
    input_modality: 'typed' as const,
    extraction_confidence: entry.confidence,
    backend_entry: entry,
  }))
  const sourceProvenance = (eventId: string | undefined) => provenance.find((entry) => entry.fact_id === eventId) ?? provenance[0] ?? {
    fact_id: eventId ?? raw.document_id,
    trust_tier: 'current_encounter' as const,
    source_document_id: null,
    original_text: 'Source information is unavailable.',
    source_language: 'unknown',
    input_modality: 'typed' as const,
    extraction_confidence: 0,
  }
  return {
    document_id: raw.document_id,
    document_type: raw.document_type,
    status: raw.status,
    sections: raw.sections,
    flags_for_physician_review: raw.flags_for_physician_review.map((flag) => ({
      type: flag.code,
      conflict_id: null,
      risk_level: flag.severity === 'high' || flag.severity === 'medium' ? flag.severity : null,
      description: flag.message,
      source_provenance: sourceProvenance(flag.source_event_ids[0]),
    })),
    provenance_map: provenance,
    validation_result: { passed: raw.validation_result.passed, failures: raw.validation_result.failures.map((failure) => failure.message), auto_regeneration_attempts: raw.validation_result.auto_regeneration_attempts },
    generated_at: raw.generated_at,
    finalized_at: raw.finalized_at ?? null,
    generator: raw.generator,
  }
}

export interface Step2ProcessRequest {
  document_id: string
  patient_id: string
  encounter_id: string
  step1_output: Step1Output
}

export const processStep2 = (request?: Step2ProcessRequest): Promise<Step2Response> => {
  if (useFixtures) return resolved(clinicalEventFixture)
  if (!request) return Promise.reject(new Error('Step2 processing requires the Step1 document context.'))
  return apiClient.postJson<Step2Response>('/api/v1/step2/process', request)
}

export const getStep2Job = (documentId?: string): Promise<Step2Response> => {
  if (useFixtures) return resolved(clinicalEventFixture)
  if (!documentId) return Promise.reject(new Error('document_id is required to load Step2 output.'))
  return apiClient.get<Step2Response>(`/api/v1/step2/process/${encodeURIComponent(documentId)}`)
}
export const validateClinicalEvents = (events: ClinicalEvent[]): Promise<ClinicalEvent[]> => resolved(events)
export const writeMemoryEvents = (request?: MemoryWriteRequest): Promise<MemoryWriteResponse> => {
  if (useFixtures) return resolved(memoryWriteFixture)
  if (!request) return Promise.reject(new Error('Memory write payload is required.'))
  return apiClient.postJson<MemoryWriteResponse>('/api/v1/step3/memory/events', { ...request, clinical_events: request.clinical_events.map(backendEventPayload) })
}
export const retrieveMemory = async (request?: MemoryRetrieveRequest): Promise<RetrievedContext> => {
  if (useFixtures) return resolved(retrievedContextFixture)
  if (!request) throw new Error('Memory retrieval context is required.')
  const response = await apiClient.postJson<BackendRetrievedContext>('/api/v1/step3/memory/retrieve', request)
  const facts = await getMemoryEvents(request.patient_id)
  return toRetrievedContext(response, facts)
}
export const getMemoryEvents = async (patientId?: string): Promise<MemoryFact[]> => {
  if (useFixtures) return resolved(memoryEventsFixture)
  if (!patientId) throw new Error('patient_id is required to load memory events.')
  const response = await apiClient.get<{ patient_id: string; events: BackendMemoryEvent[] }>(`/api/v1/step3/memory/${encodeURIComponent(patientId)}/events`)
  return response.events.map(toMemoryFact)
}
export const getPatientState = async (patientId?: string): Promise<MemoryFact[]> => {
  if (useFixtures) return resolved([retrievedContextFixture.verified_context.conditions[0], retrievedContextFixture.verified_context.medications[0], retrievedContextFixture.verified_context.allergies[0], retrievedContextFixture.verified_context.lab_trends[0]].filter((fact): fact is MemoryFact => fact !== undefined))
  if (!patientId) throw new Error('patient_id is required to load patient state.')
  const [state, events] = await Promise.all([
    apiClient.get<{ patient_id: string; concept_threads: Array<{ latest_event_id: string }> }>(`/api/v1/step3/memory/${encodeURIComponent(patientId)}/current-state`),
    getMemoryEvents(patientId),
  ])
  const latest = new Set(state.concept_threads.map((thread) => thread.latest_event_id))
  return events.filter((event) => latest.has(event.event_id))
}
export const getConflictList = async (patientId?: string): Promise<RetrievedContext['conflicts']> => {
  if (useFixtures) return resolved(retrievedContextFixture.conflicts)
  const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
  const response = await apiClient.get<BackendConflict[]>(`/api/v1/step3/conflicts${query}`)
  const facts = patientId ? await getMemoryEvents(patientId) : []
  return response.map((conflict) => toConflict(conflict, facts))
}
export const resolveConflict = async (conflictId: string, request: ConflictResolutionRequest): Promise<ConflictResolutionResponse> => {
  if (useFixtures) return resolved({ conflict_id: conflictId, status: request.resolution_action === 'keep_unresolved' ? 'dismissed' : 'resolved', new_event_id: request.resolution_action === 'keep_unresolved' ? null : 'mem_evt_resolution_001' })
  const response = await apiClient.postJson<{ conflict_id: string; status: 'resolved' | 'unresolved'; new_event_id: string | null }>(`/api/v1/step3/conflicts/${encodeURIComponent(conflictId)}/resolve`, request)
  return { ...response, status: response.status === 'unresolved' ? 'unresolved' : 'resolved' }
}
export const approveTier3 = (eventId: string, physicianId: string): Promise<Tier3ApprovalResponse> => useFixtures
  ? resolved({ event_id: eventId, new_trust_tier: 2, trust_tier_change_event_id: 'mem_evt_tier_change_001' })
  : apiClient.postJson<Tier3ApprovalResponse>(`/api/v1/step3/tier3/${encodeURIComponent(eventId)}/approve`, { physician_id: physicianId })
export const rejectTier3 = (eventId: string, physicianId: string): Promise<Tier3RejectionResponse> => useFixtures
  ? resolved({ event_id: eventId, trust_tier: 3, reviewed_status: 'reviewed_rejected' })
  : apiClient.postJson<Tier3RejectionResponse>(`/api/v1/step3/tier3/${encodeURIComponent(eventId)}/reject`, { physician_id: physicianId })

export function generateDocument(request: DocumentGenerationRequest): Promise<GeneratedDocument> {
  if (!useFixtures) {
    return apiClient.postJson<BackendGeneratedDocument>('/api/v1/step4/documents/generate', {
      ...request,
      current_consultation_events: request.current_consultation_events.map(backendEventPayload),
      retrieved_context: backendRetrievedContext(request.retrieved_context),
    }).then(normalizeGeneratedDocument)
  }
  const fixture = request.document_type === 'soap_note' ? soapDocumentFixture : dischargeDocumentFixture
  const generated = { ...fixture, document_id: fixture.document_id, generated_at: new Date().toISOString() }
  documentHistory = documentHistory.map((item) => item.document_id === generated.document_id ? { ...generated, finalized_at: item.finalized_at } : item)
  return resolved(generated)
}

export function getDocumentDraft(documentId = soapDocumentFixture.document_id): Promise<GeneratedDocument> {
  if (!useFixtures) return Promise.reject(new Error('The gateway contract does not expose a document draft read endpoint.'))
  return resolved(documentHistory.find((document) => document.document_id === documentId) ?? soapDocumentFixture)
}

export function listDocuments(): Promise<DocumentHistoryItem[]> { return useFixtures ? resolved(documentHistory) : resolved([]) }

export function finalizeDocument(documentId: string, request: FinalizationRequest): Promise<FinalizationResponse> {
  if (!useFixtures) {
    return apiClient.postJson<{ document_id: string; status: 'draft' | 'finalized'; finalized_at?: string | null; memory_write_payload?: MemoryWriteRequest; document?: BackendGeneratedDocument }>(`/api/v1/step4/documents/${encodeURIComponent(documentId)}/finalize`, {
      ...request,
      edited_sections: request.edited_sections,
    }).then((response) => response.status === 'draft'
      ? { document_id: response.document_id, status: 'discarded', next_action: 'Review the regenerated draft.' }
      : { document_id: response.document_id, status: 'finalized', finalized_at: response.finalized_at ?? new Date().toISOString(), memory_write_payload: response.memory_write_payload!, memory_write_committed: true })
  }
  if (request.action === 'reject_regenerate') return resolved({ document_id: documentId, status: 'discarded', next_action: 'Regenerate with regenerate_notes as physician_instructions' })
  const document = documentHistory.find((item) => item.document_id === documentId) ?? soapDocumentFixture
  const finalizedAt = new Date().toISOString()
  documentHistory = documentHistory.map((item) => item.document_id === documentId ? { ...item, status: 'finalized', finalized_at: finalizedAt } : item)
  return resolved({ document_id: document.document_id, status: 'finalized', finalized_at: finalizedAt, memory_write_payload: { patient_id: clinicalEventFixture.patient_id, encounter_id: clinicalEventFixture.encounter_id, source: 'physician_approved_consultation', clinical_events: physicianApprovedEvents } })
}

export function regenerateDocument(request: DocumentGenerationRequest): Promise<GeneratedDocument> { return generateDocument(request) }
