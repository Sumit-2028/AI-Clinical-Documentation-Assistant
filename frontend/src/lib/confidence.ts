import type { ExtractedField } from '../contracts/step1Output'

export type ConfidencePresentation = 'verified' | 'review' | 'high-risk'

export function getConfidencePresentation(field: ExtractedField): ConfidencePresentation {
  const autoPassThreshold = field.is_high_risk_field ? 0.95 : 0.9
  if (field.requires_doctor_review_before_memory_write || field.review_status === 'review_required' || field.review_status === 'pending' || field.extraction_confidence < autoPassThreshold) return field.is_high_risk_field ? 'high-risk' : 'review'
  return 'verified'
}

export function getConfidenceLabel(field: ExtractedField): string {
  if (field.is_high_risk_field && field.extraction_confidence < 0.95) return 'Doctor review required'
  if (field.extraction_confidence < 0.8) return 'Mandatory review'
  if (field.extraction_confidence < 0.9) return field.dual_run_result === 'agree' ? 'Dual-run agreed · review' : 'Dual-run required'
  return 'Auto-passed'
}

export function formatConfidence(value: number): string { return `${Math.round(value * 100)}%` }
