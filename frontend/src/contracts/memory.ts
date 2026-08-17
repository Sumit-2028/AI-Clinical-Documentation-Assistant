import type { ClinicalAssertion, ClinicalEvent, ClinicalStatus } from './clinicalEvent'
import type { InputModality, ISODate, RiskLevel, TrustTier } from './common'

export type MemoryReviewedStatus = 'not_applicable' | 'never_reviewed' | 'reviewed_rejected'
export type ThreadMatchConfidence = 'high' | 'low' | 'unknown'

export interface MemoryFact {
  event_id: string
  concept_thread_id: string
  normalized_concept: string
  snomed_ct_id: string | null
  entity_type: string
  clinical_domain: string
  assertion: ClinicalAssertion
  clinical_status: ClinicalStatus
  temporal_context: string
  trust_tier: TrustTier
  reviewed_status: MemoryReviewedStatus
  thread_match_confidence: ThreadMatchConfidence
  source_document_id: string
  source_text_span: { start: number; end: number }
  input_modality: InputModality
  source_language: string
  translation_confidence: number | null
  extraction_confidence: number
  contextualization_confidence: number
  event_timestamp: ISODate
  ingestion_timestamp: ISODate
  medication_attributes: { dosage: string | null; frequency: string | null; route: string | null }
  lab_attributes?: { test_name: string | null; value: string | null; unit: string | null }
  provenance?: Record<string, unknown>
}

export interface MemoryWriteRequest {
  patient_id: string
  encounter_id: string
  source: 'simulated_abha' | 'patient_upload' | 'physician_approved_consultation'
  clinical_events: ClinicalEvent[]
}

export interface WrittenMemoryEvent {
  event_id: string
  concept_thread_id: string
  trust_tier: TrustTier
  thread_match_confidence: ThreadMatchConfidence
  thread_match_method: 'code_system' | 'normalized_name_fallback'
  is_new_thread: boolean
}

export interface DetectedMemoryConflict {
  conflict_id: string
  concept_thread_id: string
  event_a_id: string
  event_b_id: string
  conflict_type: 'assertion_mismatch' | 'clinical_status_mismatch' | 'cross_category_high_risk'
  risk_level: RiskLevel
  status: 'unresolved'
}

export interface RejectedMemoryEvent { event_local_id: string; reason: string }
export interface MemoryWriteResponse { written_events: WrittenMemoryEvent[]; conflicts_detected: DetectedMemoryConflict[]; rejected_events: RejectedMemoryEvent[] }
export interface MemoryEvent extends MemoryFact { memory_event_id: string }

export interface MemoryRetrieveRequest { patient_id: string; encounter_id: string; query_concepts: string[] }
export interface ConflictResolutionRequest { resolution_action: 'confirm_event_a' | 'confirm_event_b' | 'keep_unresolved'; physician_id: string }
export interface ConflictResolutionResponse { conflict_id: string; status: 'resolved' | 'dismissed' | 'unresolved'; new_event_id: string | null }
export interface Tier3ApprovalResponse { event_id: string; new_trust_tier: 2; trust_tier_change_event_id: string }
export interface Tier3RejectionResponse { event_id: string; trust_tier: 3; reviewed_status: 'reviewed_rejected' }

export type ConflictSummary = import('./retrievedContext').Conflict
