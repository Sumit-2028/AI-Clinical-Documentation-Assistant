import type { Patient, PatientCreateRequest } from '../contracts/patient'
import { apiClient } from './client'

export function createPatient(request: PatientCreateRequest): Promise<Patient> {
  return apiClient.postJson<Patient>('/api/v1/patients', request)
}

export function getPatient(patientId: string): Promise<Patient> {
  return apiClient.get<Patient>(`/api/v1/patients/${encodeURIComponent(patientId)}`)
}
