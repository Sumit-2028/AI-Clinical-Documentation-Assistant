import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { finalizeDocument, generateDocument, getDocumentDraft, listDocuments, regenerateDocument, writeMemoryEvents } from '../api'
import type { DocumentGenerationRequest, FinalizationRequest } from '../contracts/documents'
import type { MemoryWriteRequest } from '../contracts/memory'

export function useDocumentHistory() { return useQuery({ queryKey: ['documents'], queryFn: listDocuments }) }
export function useDocumentDraft(documentId?: string) { return useQuery({ queryKey: ['document-draft', documentId], queryFn: () => getDocumentDraft(documentId), enabled: Boolean(documentId) }) }
export function useGenerateDocument() {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (request: DocumentGenerationRequest) => generateDocument(request), onSuccess: (document) => { queryClient.setQueryData(['document-draft', document.document_id], document); void queryClient.invalidateQueries({ queryKey: ['documents'] }) } })
}
export function useRegenerateDocument() {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (request: DocumentGenerationRequest) => regenerateDocument(request), onSuccess: (document) => { queryClient.setQueryData(['document-draft', document.document_id], document); void queryClient.invalidateQueries({ queryKey: ['documents'] }) } })
}
export function useFinalizeDocument() {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: ({ documentId, request }: { documentId: string; request: FinalizationRequest }) => finalizeDocument(documentId, request), onSuccess: (response) => { queryClient.setQueryData(['document-finalization', response.document_id], response); void queryClient.invalidateQueries({ queryKey: ['documents'] }) } })
}
export function useWriteFinalizedMemory() {
  return useMutation({ mutationFn: (payload: MemoryWriteRequest) => writeMemoryEvents(payload) })
}
