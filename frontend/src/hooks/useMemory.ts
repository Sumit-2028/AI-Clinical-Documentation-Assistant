import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { approveTier3, getConflictList, getMemoryEvents, getPatientState, rejectTier3, resolveConflict, retrieveMemory } from '../api'
import type { ConflictResolutionRequest } from '../contracts/memory'

export function useRetrievedContext(queryConcepts: string[] = ['chest pain'], patientId = import.meta.env.MODE === 'test' ? 'pat_00123' : '', encounterId = import.meta.env.MODE === 'test' ? 'enc_2026_0817_01' : '') {
  return useQuery({ queryKey: ['retrieved-context', patientId, encounterId, queryConcepts], queryFn: () => retrieveMemory({ patient_id: patientId, encounter_id: encounterId, query_concepts: queryConcepts }), enabled: Boolean(patientId && encounterId) })
}
export function useMemoryEvents(patientId = import.meta.env.MODE === 'test' ? 'pat_00123' : '') { return useQuery({ queryKey: ['memory-events', patientId], queryFn: () => getMemoryEvents(patientId), enabled: Boolean(patientId) }) }
export function usePatientState(patientId = import.meta.env.MODE === 'test' ? 'pat_00123' : '') { return useQuery({ queryKey: ['patient-state', patientId], queryFn: () => getPatientState(patientId), enabled: Boolean(patientId) }) }
export function useConflictList(patientId = import.meta.env.MODE === 'test' ? 'pat_00123' : '') { return useQuery({ queryKey: ['memory-conflicts', patientId], queryFn: () => getConflictList(patientId), enabled: Boolean(patientId) }) }
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
