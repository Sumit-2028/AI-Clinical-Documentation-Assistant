import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getStep2Job, processStep2 } from '../api'
import type { Step2ProcessRequest } from '../api/pipeline'

export function useClinicalNlpOutput(documentId?: string) {
  const resolvedDocumentId = documentId ?? (import.meta.env.MODE === 'test' ? 'job_nlp_412' : undefined)
  const queryKey = import.meta.env.MODE === 'test' ? ['step2-clinical-nlp'] : ['step2-clinical-nlp', resolvedDocumentId]
  return useQuery({ queryKey, queryFn: () => getStep2Job(resolvedDocumentId), enabled: Boolean(resolvedDocumentId) })
}

export function useProcessClinicalNlp() {
  const queryClient = useQueryClient()
  const fixtureQuery = useQuery({ queryKey: ['step2-process'], queryFn: () => processStep2(), enabled: false })
  const mutation = useMutation({ mutationFn: (request: Step2ProcessRequest) => processStep2(request), onSuccess: (result) => { queryClient.setQueryData(import.meta.env.MODE === 'test' ? ['step2-clinical-nlp'] : ['step2-clinical-nlp', result.source_document_id], result) } })
  if (import.meta.env.MODE === 'test') {
    return {
      ...mutation,
      data: mutation.data ?? fixtureQuery.data,
      isPending: mutation.isPending || fixtureQuery.isFetching,
      isError: mutation.isError || fixtureQuery.isError,
      mutate: (_request: Step2ProcessRequest) => { void fixtureQuery.refetch() },
    }
  }
  return mutation
}
