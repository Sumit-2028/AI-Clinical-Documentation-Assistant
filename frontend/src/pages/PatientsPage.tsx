import { useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { createPatient, getPatient } from '../api/patients'
import type { Patient } from '../contracts/patient'
import { SectionCard } from '../components/SectionCard'

function messageFor(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 403) return 'You are not authorized to access this patient.'
  if (error instanceof ApiError && error.status === 404) return 'Patient not found or not assigned to your workspace.'
  return error instanceof Error ? error.message : fallback
}

export function PatientsPage() {
  const [patientId, setPatientId] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [patient, setPatient] = useState<Patient | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [createdMessage, setCreatedMessage] = useState<string | null>(null)

  const lookup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!patientId.trim()) return
    setError(null)
    setCreatedMessage(null)
    setPatient(null)
    setIsLoading(true)
    try {
      setPatient(await getPatient(patientId.trim()))
    } catch (reason) {
      setError(messageFor(reason, 'Unable to retrieve the patient.'))
    } finally {
      setIsLoading(false)
    }
  }

  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!displayName.trim()) return
    setError(null)
    setCreatedMessage(null)
    setIsLoading(true)
    try {
      const created = await createPatient({ display_name: displayName.trim() })
      setPatient(created)
      setPatientId(created.patient_id)
      setDisplayName('')
      setCreatedMessage('Patient created and assigned to your workspace.')
    } catch (reason) {
      setError(messageFor(reason, 'Unable to create the patient.'))
    } finally {
      setIsLoading(false)
    }
  }

  return <div className="page-stack">
    <div className="dashboard-welcome"><div><p className="eyebrow">PATIENT ACCESS</p><h1>Patients</h1><p className="page-subtitle">Use the backend-issued patient ID to open an authorized patient record.</p></div></div>
    <div className="dashboard-grid">
      <SectionCard title="Create patient" eyebrow="NEW RECORD">
        <form onSubmit={create} className="auth-field-grid">
          <label className="auth-field"><span>Patient display name</span><input value={displayName} onChange={(event) => setDisplayName(event.target.value)} minLength={2} maxLength={255} required /></label>
          <button className="primary-button" type="submit" disabled={isLoading}>{isLoading ? 'Saving…' : 'Create patient'}</button>
        </form>
      </SectionCard>
      <SectionCard title="Find patient" eyebrow="AUTHORIZED LOOKUP">
        <form onSubmit={lookup}>
          <label className="auth-field"><span>Patient ID</span><input value={patientId} onChange={(event) => setPatientId(event.target.value)} placeholder="Backend-issued UUID" required /></label>
          <button className="primary-button" type="submit" disabled={isLoading}>{isLoading ? 'Loading…' : 'Open patient'}</button>
        </form>
      </SectionCard>
    </div>
    {error && <p className="auth-status auth-error" role="alert">{error}</p>}
    {createdMessage && <p className="auth-status" role="status">{createdMessage}</p>}
    {patient && <SectionCard title={patient.display_name || 'Patient record'} eyebrow="AUTHORIZED PATIENT"><p><strong>Patient ID:</strong> {patient.patient_id}</p><p>This identity is issued and persisted by the backend.</p></SectionCard>}
  </div>
}
