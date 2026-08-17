import type { ClinicalEvent } from './clinicalEvent'
import type { MemoryWriteRequest } from './memory'
import type { RetrievedContext } from './retrievedContext'
import type { ISODate, InputModality } from './common'

export type DocumentType = 'soap_note' | 'discharge_summary'
export type DocumentStatus = 'draft' | 'validation_failed' | 'finalized' | 'discarded'
export type DocumentTrustTier = 1 | 2 | 3 | 'current_encounter'

export interface DocumentSections {
  subjective: string | null
  objective: string | null
  assessment: string | null
  plan: string | null
  patient_identification: string | null
  reason_for_encounter: string | null
  medications: string | null
  allergies: string | null
  procedures: string | null
  relevant_history: string | null
  follow_up: string | null
}

export interface DocumentProvenanceEntry {
  fact_id: string
  trust_tier: DocumentTrustTier
  source_document_id: string | null
  original_text: string
  source_language: string
  input_modality: InputModality | string
  extraction_confidence: number
}

export interface PhysicianReviewFlag {
  type: 'conflict' | 'low_confidence_thread_match' | string
  conflict_id: string | null
  risk_level: 'high' | 'medium' | null
  description: string
  source_provenance: DocumentProvenanceEntry
}

export interface DocumentValidationResult {
  passed: boolean
  failures: string[]
  auto_regeneration_attempts: number
}

export interface GeneratedDocument {
  document_id: string
  document_type: DocumentType
  status: Exclude<DocumentStatus, 'discarded'>
  sections: DocumentSections
  flags_for_physician_review: PhysicianReviewFlag[]
  provenance_map: DocumentProvenanceEntry[]
  validation_result: DocumentValidationResult
  generated_at: ISODate
}

export interface DocumentGenerationRequest {
  patient_id: string
  encounter_id: string
  document_type: DocumentType
  current_consultation_events: ClinicalEvent[]
  retrieved_context: RetrievedContext
  physician_instructions: string | null
}

export interface FinalizationRequest {
  action: 'accept' | 'edit' | 'reject_regenerate'
  physician_id: string
  edited_sections: Partial<DocumentSections> | null
  regenerate_notes: string | null
}

export type DocumentFinalizationRequest = FinalizationRequest
export type MemoryWritePayload = MemoryWriteRequest

export interface FinalizedDocumentResponse {
  document_id: string
  status: 'finalized'
  finalized_at: ISODate
  memory_write_payload: MemoryWritePayload
}

export interface DiscardedDocumentResponse {
  document_id: string
  status: 'discarded'
  next_action: string
}

export type FinalizationResponse = FinalizedDocumentResponse | DiscardedDocumentResponse

export interface DocumentHistoryItem extends GeneratedDocument {
  finalized_at: ISODate | null
}
