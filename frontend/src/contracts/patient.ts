export interface Patient {
  patient_id: string
  display_name?: string | null
  user_id?: string | null
}

export interface PatientCreateRequest {
  display_name: string
}
