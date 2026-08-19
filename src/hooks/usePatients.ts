import { useQuery } from '@tanstack/react-query'
import { getPatient } from '../api'

export function usePatientRecord(patientId: string) {
  return useQuery({ queryKey: ['patient-record', patientId], queryFn: () => getPatient(patientId), enabled: Boolean(patientId) })
}
