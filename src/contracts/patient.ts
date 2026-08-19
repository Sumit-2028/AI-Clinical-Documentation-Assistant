export type PatientStatus = 'active' | 'inactive'

export type PatientValidationField = 'name' | 'abha_id' | 'phone_number'

export interface PatientRecord {
  patient_id: string
  name: string
  age: number
  gender: string
  status: PatientStatus
  encounter_id: string
  existing_context_summary: string
  abha_id: string
  phone_number: string
}

export interface CreatePatientInput {
  name: string
  abha_id: string
  phone_number: string
  age?: number
  gender?: string
}
