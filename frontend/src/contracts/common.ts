export type ISODate = string

export type InputModality = 'typed' | 'handwritten' | 'multilingual'
export type ProcessingStatus = 'complete' | 'pending_human_verification' | 'failed'
export type ConfidenceTier = 'auto_pass' | 'dual_run' | 'human_verification_required' | 'verified' | '90-100' | '80-89' | 'below-80'
export type DualRunResult = 'not_required' | 'agree' | 'disagree' | { triggered: boolean; second_pass_text?: string | null; agreement?: boolean | null }
export type ReviewStatus = 'approved' | 'review_required' | 'rejected' | 'pending'
export type TrustTier = 1 | 2 | 3
export type RiskLevel = 'high' | 'medium' | 'low'

export interface ApiError {
  error: { code: string; message: string; details: Record<string, string>; trace_id: string }
}

export interface SourceMetadata {
  source_document: string
  input_modality: InputModality
  source_language: string
  translation_confidence: number | null
}
