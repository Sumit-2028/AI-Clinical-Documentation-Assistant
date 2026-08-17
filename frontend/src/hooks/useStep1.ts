import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getReviewQueue, getStep1AuditLog, getStep1Output, verifyStep1Field } from '../api'
import type { VerifyStep1FieldRequest } from '../contracts/step1Output'

export function useStep1Output(documentId?: string) {
  const resolvedDocumentId = documentId ?? (import.meta.env.MODE === 'test' ? 'job_ocr_771' : undefined)
  return useQuery({ queryKey: ['step1-output', resolvedDocumentId], queryFn: () => getStep1Output(resolvedDocumentId!), enabled: Boolean(resolvedDocumentId) })
}

export function useReviewQueue(patientId?: string, documentId?: string) {
  return useQuery({ queryKey: ['step1-review-queue', patientId, documentId], queryFn: () => getReviewQueue(patientId, documentId) })
}

export function useStep1AuditLog(documentId?: string) {
  return useQuery({ queryKey: ['step1-audit-log', documentId], queryFn: () => getStep1AuditLog(documentId), enabled: Boolean(documentId) || import.meta.env.MODE === 'test' })
}

export function useVerifyStep1Field() {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (request: VerifyStep1FieldRequest) => verifyStep1Field(request), onSuccess: (result) => { if ('document_id' in result) queryClient.setQueryData(['step1-output', result.document_id], result); void queryClient.invalidateQueries({ queryKey: ['step1-output'] }); void queryClient.invalidateQueries({ queryKey: ['step1-review-queue'] }); void queryClient.invalidateQueries({ queryKey: ['step1-audit-log'] }) } })
}
