import type { InputModality } from '../contracts/common'
import type { Step1AuditLog, Step1Output, UploadDocumentRequest, UploadDocumentResponse, VerificationResponse, VerifyStep1FieldRequest } from '../contracts/step1Output'
import step1Fixture from '../mocks/step1-output.json'

let step1State: Step1Output = step1Fixture as unknown as Step1Output

const pause = (milliseconds = 180): Promise<void> => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

export async function uploadTypedDocument(request: UploadDocumentRequest): Promise<UploadDocumentResponse> {
  return uploadDocument({ ...request, modality: 'typed' })
}

export async function uploadHandwrittenDocument(request: UploadDocumentRequest): Promise<UploadDocumentResponse> {
  return uploadDocument({ ...request, modality: 'handwritten' })
}

export async function uploadMultilingualInput(request: UploadDocumentRequest): Promise<UploadDocumentResponse> {
  return uploadDocument({ ...request, modality: 'multilingual' })
}

async function uploadDocument(request: UploadDocumentRequest): Promise<UploadDocumentResponse> {
  await pause()
  return { document_id: step1State.document_id, job_id: step1State.job_id, processing_status: request.modality === 'typed' ? 'complete' : 'pending_human_verification' }
}

export async function getStep1Document(_documentId: string): Promise<Step1Output> { await pause(); return step1State }
export async function getStep1Output(_jobId: string): Promise<Step1Output> { await pause(); return step1State }

export async function verifyStep1Field(request: VerifyStep1FieldRequest): Promise<VerificationResponse> {
  await pause()
  const field = step1State.extracted_fields.find((item) => item.field_id === request.field_id)
  if (!field) throw new Error('The extracted field could not be found.')
  const verifiedText = request.verified_text.trim()
  const updatedFields = step1State.extracted_fields.map((field) => field.field_id === request.field_id
    ? { ...field, standardized_text: request.approved ? verifiedText : field.standardized_text, verified_text: request.approved ? verifiedText : null, review_status: request.approved ? 'approved' as const : 'rejected' as const, requires_doctor_review_before_memory_write: false }
    : field)
  const reviewComplete = updatedFields.every((item) => !item.requires_doctor_review_before_memory_write && item.review_status !== 'review_required' && item.review_status !== 'pending')
  step1State = { ...step1State, extracted_fields: updatedFields, processing_status: reviewComplete ? 'complete' : 'pending_human_verification', updated_at: new Date().toISOString(), written_to_memory: reviewComplete && updatedFields.every((item) => item.review_status === 'approved') }
  return { status: request.approved ? 'verified' : 'rejected', written_to_memory: step1State.written_to_memory, audit_log_id: 'aud_9910' }
}

export async function getReviewQueue(_patientId?: string): Promise<Step1Output[]> {
  await pause()
  return step1State.processing_status === 'pending_human_verification' ? [step1State] : []
}

export async function getStep1AuditLog(): Promise<Step1AuditLog> {
  await pause()
  return { audit_log_id: 'aud_9910', document_id: step1State.document_id, patient_id: step1State.patient_id, encounter_id: step1State.encounter_id, processing_status: step1State.processing_status, created_at: step1State.created_at, fields: step1State.extracted_fields.map(({ field_id, extraction_confidence, review_status, is_high_risk_field }) => ({ field_id, extraction_confidence, review_status, is_high_risk_field })) }
}

export function getEngineForModality(modality: InputModality): 'OCR engine' | 'Gemini 2.5 Pro VLM' {
  return modality === 'typed' ? 'OCR engine' : 'Gemini 2.5 Pro VLM'
}
