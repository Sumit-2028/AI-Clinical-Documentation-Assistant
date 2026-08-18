import { useQuery } from '@tanstack/react-query'
import { getPatient, listPatients } from '../api/patients'

export function usePatients(activePatientId?: string) {
  return useQuery({
    queryKey: ['patients', activePatientId ?? ''],
    queryFn: () => listPatients(activePatientId ? [activePatientId] : []),
  })
}

export function usePatient(patientId?: string) {
  return useQuery({
    queryKey: ['patient', patientId],
    queryFn: () => getPatient(patientId!),
    enabled: Boolean(patientId),
  })
}
