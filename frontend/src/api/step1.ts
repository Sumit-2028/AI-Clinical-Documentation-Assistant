import type { InputModality } from '../contracts/common'
import type { Step1AuditLog, Step1Output, UploadDocumentRequest, UploadDocumentResponse, VerificationResponse, VerifyStep1FieldRequest } from '../contracts/step1Output'
import step1Fixture from '../mocks/step1-output.json'
import { apiClient } from './client'

const useFixtures = import.meta.env.MODE === 'test'
let step1State: Step1Output = step1Fixture as unknown as Step1Output

const pause = (milliseconds = 180): Promise<void> => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

export async function uploadTypedDocument(request: UploadDocumentRequest): Promise<UploadDocumentResponse> {
  return uploadDocument({ ...request, modality: 'typed' })
}

export async function uploadHandwrittenDocument(request: UploadDocumentRequest): Promise<UploadDocumentResponse> {
  return uploadDocument({ ...request, modality: 'handwritten' })
}

export async function uploadMultilingualInput(request: UploadDocumentRequest): Promise<UploadDocumentResponse> {
  if (useFixtures) return uploadDocument({ ...request, modality: 'multilingual' })
  if (!request.text_input?.trim()) throw new Error('Multilingual input text is required.')
  const output = await apiClient.postJson<Step1Output>('/api/v1/step1/documents/multilingual', {
    patient_id: request.patient_id,
    encounter_id: request.encounter_id,
    text_input: request.text_input,
    source_language: request.source_language ?? 'en',
  })
  return toUploadResponse(output)
}

async function uploadDocument(request: UploadDocumentRequest): Promise<UploadDocumentResponse> {
  if (useFixtures) {
    await pause()
    return { document_id: step1State.document_id, job_id: step1State.job_id, processing_status: request.modality === 'typed' ? 'complete' : 'pending_human_verification', step1_output: step1State }
  }
  if (!request.file) throw new Error('A document file is required.')
  const form = new FormData()
  form.append('patient_id', request.patient_id)
  form.append('encounter_id', request.encounter_id)
  form.append('file', request.file, request.file.name)
  const path = request.modality === 'handwritten' ? '/api/v1/step1/documents/handwritten' : '/api/v1/step1/documents/typed'
  const output = await apiClient.postForm<Step1Output>(path, form)
  return toUploadResponse(output)
}

function toUploadResponse(output: Step1Output): UploadDocumentResponse {
  return { document_id: output.document_id, processing_status: output.processing_status, step1_output: output }
}

export async function getStep1Document(documentId: string): Promise<Step1Output> {
  if (useFixtures) { await pause(); return step1State }
  return apiClient.get<Step1Output>(`/api/v1/step1/documents/${encodeURIComponent(documentId)}`)
}

/** The backend identifies Step 1 records by document_id; the old adapter name is retained. */
export async function getStep1Output(documentId: string): Promise<Step1Output> {
  return getStep1Document(documentId)
}

export async function verifyStep1Field(request: VerifyStep1FieldRequest): Promise<VerificationResponse | Step1Output> {
  if (useFixtures) {
    await pause()
    const updatedFields = step1State.extracted_fields.map((field) => field.field_id === request.field_id
      ? { ...field, verified_text: request.verified_text, review_status: request.approved ? 'approved' as const : 'rejected' as const, requires_doctor_review_before_memory_write: false }
      : field)
    step1State = { ...step1State, extracted_fields: updatedFields, updated_at: new Date().toISOString(), written_to_memory: updatedFields.every((field) => field.review_status === 'approved' || field.review_status === 'rejected') }
    return { status: request.approved ? 'verified' : 'rejected', written_to_memory: step1State.written_to_memory ?? false, audit_log_id: 'aud_9910' }
  }
  if (!request.document_id) throw new Error('document_id is required for human verification.')
  return apiClient.postJson<Step1Output>(`/api/v1/step1/documents/${encodeURIComponent(request.document_id)}/human-verify`, {
    field_id: request.field_id,
    verified_text: request.verified_text,
    reviewer_id: request.reviewer_id,
    approved: request.approved,
  })
}

/** There is no separate review queue endpoint in the authoritative gateway contract. */
export async function getReviewQueue(patientId?: string, documentId?: string): Promise<Step1Output[]> {
  if (useFixtures) { await pause(); return step1State.processing_status === 'pending_human_verification' ? [step1State] : [] }
  if (!documentId) return []
  const output = await getStep1Document(documentId)
  return output.patient_id === patientId && output.processing_status === 'pending_human_verification' ? [output] : []
}

export async function getStep1AuditLog(documentId?: string): Promise<Step1AuditLog> {
  if (useFixtures) {
    await pause()
    return { audit_log_id: step1State.audit_log_id ?? 'aud_9910', document_id: step1State.document_id, patient_id: step1State.patient_id, encounter_id: step1State.encounter_id, processing_status: step1State.processing_status, created_at: step1State.created_at, fields: step1State.extracted_fields.map(({ field_id, extraction_confidence, review_status, is_high_risk_field }) => ({ field_id, extraction_confidence, review_status, is_high_risk_field })) }
  }
  if (!documentId) throw new Error('document_id is required to load audit information.')
  const output = await getStep1Document(documentId)
  return { audit_log_id: output.audit_log_id ?? output.document_id, document_id: output.document_id, patient_id: output.patient_id, encounter_id: output.encounter_id, processing_status: output.processing_status, created_at: output.created_at, fields: output.extracted_fields.map(({ field_id, extraction_confidence, review_status, is_high_risk_field }) => ({ field_id, extraction_confidence, review_status, is_high_risk_field })) }
}

export function getEngineForModality(modality: InputModality): 'OCR engine' | 'Gemini 2.5 Pro VLM' {
  return modality === 'typed' ? 'OCR engine' : 'Gemini 2.5 Pro VLM'
}
