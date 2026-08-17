import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getReviewQueue, getStep1AuditLog, getStep1Output, verifyStep1Field } from '../api'
import type { VerifyStep1FieldRequest } from '../contracts/step1Output'

export function useStep1Output() {
  return useQuery({ queryKey: ['step1-output'], queryFn: () => getStep1Output('job_ocr_771') })
}

export function useReviewQueue() {
  return useQuery({ queryKey: ['step1-review-queue'], queryFn: () => getReviewQueue('pat_00123') })
}

export function useStep1AuditLog() {
  return useQuery({ queryKey: ['step1-audit-log'], queryFn: getStep1AuditLog })
}

export function useVerifyStep1Field() {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (request: VerifyStep1FieldRequest) => verifyStep1Field(request), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['step1-output'] }); void queryClient.invalidateQueries({ queryKey: ['step1-review-queue'] }); void queryClient.invalidateQueries({ queryKey: ['step1-audit-log'] }) } })
}
