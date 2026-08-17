import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { approveTier3, getConflictList, getMemoryEvents, getPatientState, rejectTier3, resolveConflict, retrieveMemory } from '../api'
import type { ConflictResolutionRequest } from '../contracts/memory'

export function useRetrievedContext(queryConcepts: string[] = ['chest pain'], patientId = 'pat_00123', encounterId = 'enc_2026_0817_01') {
  return useQuery({ queryKey: ['retrieved-context', patientId, encounterId, queryConcepts], queryFn: () => retrieveMemory({ patient_id: patientId, encounter_id: encounterId, query_concepts: queryConcepts }) })
}
export function useMemoryEvents() { return useQuery({ queryKey: ['memory-events', 'pat_00123'], queryFn: () => getMemoryEvents('pat_00123') }) }
export function usePatientState() { return useQuery({ queryKey: ['patient-state', 'pat_00123'], queryFn: () => getPatientState('pat_00123') }) }
export function useConflictList() { return useQuery({ queryKey: ['memory-conflicts', 'pat_00123'], queryFn: () => getConflictList('pat_00123') }) }
export function useResolveConflict() {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: ({ conflictId, request }: { conflictId: string; request: ConflictResolutionRequest }) => resolveConflict(conflictId, request), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['retrieved-context'] }); void queryClient.invalidateQueries({ queryKey: ['memory-conflicts'] }) } })
}
export function useApproveTier3() {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: ({ eventId, physicianId }: { eventId: string; physicianId: string }) => approveTier3(eventId, physicianId), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['retrieved-context'] }) } })
}
export function useRejectTier3() {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: ({ eventId, physicianId }: { eventId: string; physicianId: string }) => rejectTier3(eventId, physicianId), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['retrieved-context'] }) } })
}
