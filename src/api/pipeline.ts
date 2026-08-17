import type { ClinicalEvent, Step2Response } from '../contracts/clinicalEvent'
import type { DocumentGenerationRequest, DocumentHistoryItem, FinalizationRequest, FinalizationResponse, GeneratedDocument } from '../contracts/documents'
import type { ConflictResolutionRequest, ConflictResolutionResponse, MemoryFact, MemoryRetrieveRequest, MemoryWriteRequest, MemoryWriteResponse, Tier3ApprovalResponse, Tier3RejectionResponse } from '../contracts/memory'
import type { RetrievedContext } from '../contracts/retrievedContext'
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

export const processStep2 = (): Promise<Step2Response> => resolved(clinicalEventFixture)
export const getStep2Job = (_jobId?: string): Promise<Step2Response> => resolved(clinicalEventFixture)
export const validateClinicalEvents = (events: ClinicalEvent[]): Promise<ClinicalEvent[]> => resolved(events)
export const writeMemoryEvents = (_request?: MemoryWriteRequest): Promise<MemoryWriteResponse> => resolved(memoryWriteFixture)
export const retrieveMemory = (_request?: MemoryRetrieveRequest): Promise<RetrievedContext> => resolved(retrievedContextFixture)
export const getMemoryEvents = (_patientId?: string): Promise<MemoryFact[]> => resolved(memoryEventsFixture)
export const getPatientState = (_patientId?: string): Promise<MemoryFact[]> => resolved([retrievedContextFixture.verified_context.conditions[0], retrievedContextFixture.verified_context.medications[0], retrievedContextFixture.verified_context.allergies[0], retrievedContextFixture.verified_context.lab_trends[0]].filter((fact): fact is MemoryFact => fact !== undefined))
export const getConflictList = (_patientId?: string): Promise<RetrievedContext['conflicts']> => resolved(retrievedContextFixture.conflicts)
export const resolveConflict = (_conflictId: string, _request: ConflictResolutionRequest): Promise<ConflictResolutionResponse> => resolved({ conflict_id: _conflictId, status: _request.resolution_action === 'keep_unresolved' ? 'dismissed' : 'resolved', new_event_id: _request.resolution_action === 'keep_unresolved' ? null : 'mem_evt_resolution_001' })
export const approveTier3 = (eventId: string, _physicianId: string): Promise<Tier3ApprovalResponse> => resolved({ event_id: eventId, new_trust_tier: 2, trust_tier_change_event_id: 'mem_evt_tier_change_001' })
export const rejectTier3 = (eventId: string, _physicianId: string): Promise<Tier3RejectionResponse> => resolved({ event_id: eventId, trust_tier: 3, reviewed_status: 'reviewed_rejected' })

export function generateDocument(request: DocumentGenerationRequest): Promise<GeneratedDocument> {
  const fixture = request.document_type === 'soap_note' ? soapDocumentFixture : dischargeDocumentFixture
  const generated = { ...fixture, document_id: fixture.document_id, generated_at: new Date().toISOString() }
  documentHistory = documentHistory.map((item) => item.document_id === generated.document_id ? { ...generated, finalized_at: item.finalized_at } : item)
  return resolved(generated)
}

export function getDocumentDraft(documentId = soapDocumentFixture.document_id): Promise<GeneratedDocument> {
  return resolved(documentHistory.find((document) => document.document_id === documentId) ?? soapDocumentFixture)
}

export function listDocuments(): Promise<DocumentHistoryItem[]> { return resolved(documentHistory) }

export function finalizeDocument(documentId: string, request: FinalizationRequest): Promise<FinalizationResponse> {
  if (request.action === 'reject_regenerate') return resolved({ document_id: documentId, status: 'discarded', next_action: 'Regenerate with regenerate_notes as physician_instructions' })
  const document = documentHistory.find((item) => item.document_id === documentId) ?? soapDocumentFixture
  const finalizedAt = new Date().toISOString()
  documentHistory = documentHistory.map((item) => item.document_id === documentId ? { ...item, status: 'finalized', finalized_at: finalizedAt } : item)
  return resolved({ document_id: document.document_id, status: 'finalized', finalized_at: finalizedAt, memory_write_payload: { patient_id: clinicalEventFixture.patient_id, encounter_id: clinicalEventFixture.encounter_id, source: 'physician_approved_consultation', clinical_events: physicianApprovedEvents } })
}

export function regenerateDocument(request: DocumentGenerationRequest): Promise<GeneratedDocument> { return generateDocument(request) }
