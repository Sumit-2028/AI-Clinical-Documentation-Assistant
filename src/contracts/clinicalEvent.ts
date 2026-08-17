import type { InputModality, ISODate } from './common'

export type ClinicalEntityType = 'Disease' | 'Symptom' | 'Medication' | 'Allergy' | 'Procedure' | 'LabFinding' | 'LaboratoryFinding' | 'Dosage' | 'Route'
export type ClinicalAssertion = 'affirmed' | 'negated' | 'possible'
export type ClinicalStatus = 'active' | 'historical' | 'resolved' | 'unknown'
export type TemporalContextType = 'current' | 'historical' | 'future' | 'specific_date'
export type ClinicalValidationStatus = 'valid' | 'invalid_schema' | 'invalid_entity' | 'invalid_relationship' | 'incomplete_provenance'

export interface ClinicalRelationship { relation_type: string; target_event_local_id: string }
export interface AmbiguousAbbreviationResolution { was_ambiguous: boolean; resolved_value: string | null; resolution_confidence: number }
export interface MedicationAttributes { dosage: string | null; strength: string | null; frequency: string | null; route: string | null }
export interface LabAttributes { test_name: string | null; value: string | null; unit: string | null }

export interface ClinicalEvent {
  event_local_id: string
  original_text: string
  processed_text: string
  normalized_concept: string
  snomed_ct_id: string | null
  entity_type: ClinicalEntityType
  clinical_domain: string
  relationships: ClinicalRelationship[]
  assertion: ClinicalAssertion
  clinical_status: ClinicalStatus
  temporal_context: TemporalContextType
  temporal_date: ISODate | null
  bioclinicalbert_confidence: number
  gemini_contextualization_confidence: number
  ambiguous_abbreviation_resolved: AmbiguousAbbreviationResolution
  source_document_id: string
  source_text_span: { start: number; end: number }
  input_modality: InputModality
  source_language: string
  translation_confidence: number | null
  medication_attributes: MedicationAttributes
  lab_attributes: LabAttributes
  validation_status: ClinicalValidationStatus
}

export interface Step2Response {
  clinical_events: ClinicalEvent[]
  patient_id: string
  encounter_id: string
  source_document_id: string
  processed_at: ISODate
}
