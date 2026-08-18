import type { Patient, PatientCreateRequest } from '../contracts/patient'
import { apiClient } from './client'

const PATIENT_IDS_STORAGE_KEY = 'medflow.backend-patient-ids'
const useFixtures = import.meta.env.MODE === 'test'
const fixturePatient: Patient = {
  patient_id: 'pat_00123',
  display_name: 'Ananya Mehta',
}

function readRememberedPatientIds(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const value = window.localStorage.getItem(PATIENT_IDS_STORAGE_KEY)
    const parsed: unknown = value ? JSON.parse(value) : []
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string' && item.length > 0) : []
  } catch {
    return []
  }
}

/**
 * The backend contract intentionally exposes patient creation and authorized
 * lookup, but not a patient collection endpoint. Remember only IDs returned
 * by the backend so the selector can hydrate them through GET /patients/{id}.
 */
export function rememberPatient(patient: Patient): void {
  if (typeof window === 'undefined' || !patient.patient_id) return
  try {
    const ids = [...new Set([...readRememberedPatientIds(), patient.patient_id])]
    window.localStorage.setItem(PATIENT_IDS_STORAGE_KEY, JSON.stringify(ids))
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts.
  }
}

export async function createPatient(request: PatientCreateRequest): Promise<Patient> {
  const patient = await apiClient.postJson<Patient>('/api/v1/patients', request)
  rememberPatient(patient)
  return patient
}

export function getPatient(patientId: string): Promise<Patient> {
  if (useFixtures) return Promise.resolve({ ...fixturePatient, patient_id: patientId || fixturePatient.patient_id })
  return apiClient.get<Patient>(`/api/v1/patients/${encodeURIComponent(patientId)}`)
}

export async function listPatients(additionalPatientIds: string[] = []): Promise<Patient[]> {
  if (useFixtures) {
    const fixtureIds = [...new Set([fixturePatient.patient_id, ...additionalPatientIds.filter(Boolean)])]
    return Promise.all(fixtureIds.map((patientId) => getPatient(patientId)))
  }

  const patientIds = [...new Set([...readRememberedPatientIds(), ...additionalPatientIds.filter(Boolean)])]
  const patients = await Promise.all(patientIds.map((patientId) => getPatient(patientId)))
  return patients.filter((patient, index, all) => all.findIndex((item) => item.patient_id === patient.patient_id) === index)
}
