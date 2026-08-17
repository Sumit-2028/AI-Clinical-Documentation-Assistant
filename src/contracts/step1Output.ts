import type { ConfidenceTier, DualRunResult, InputModality, ISODate, ProcessingStatus, ReviewStatus } from './common'

export interface ExtractedField {
  field_id: string
  field_type: string
  raw_text: string
  standardized_text: string
  extraction_confidence: number
  is_high_risk_field: boolean
  confidence_tier: ConfidenceTier
  dual_run_result: DualRunResult
  requires_doctor_review_before_memory_write: boolean
  review_status: ReviewStatus
  verified_text: string | null
}

export interface Step1Output {
  document_id: string
  job_id: string
  patient_id: string
  encounter_id: string
  source_document: string
  input_modality: InputModality
  source_language: string
  translation_confidence: number | null
  original_language_text: string | null
  processing_status: ProcessingStatus
  extracted_fields: ExtractedField[]
  created_at: ISODate
  updated_at: ISODate
  written_to_memory: boolean
}

export interface UploadDocumentRequest {
  patient_id: string
  encounter_id: string
  modality: InputModality
  source_language?: string
}

export interface UploadDocumentResponse {
  document_id: string
  job_id: string
  processing_status: ProcessingStatus
}

export interface VerifyStep1FieldRequest {
  field_id: string
  verified_text: string
  reviewer_id: string
  approved: boolean
}

export interface VerificationResponse {
  status: 'verified' | 'rejected'
  written_to_memory: boolean
  audit_log_id: string
}

export interface Step1AuditLog {
  audit_log_id: string
  document_id: string
  patient_id: string
  encounter_id: string
  processing_status: ProcessingStatus
  created_at: ISODate
  fields: Array<Pick<ExtractedField, 'field_id' | 'extraction_confidence' | 'review_status' | 'is_high_risk_field'>>
}
