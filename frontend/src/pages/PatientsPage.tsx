import { useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { createPatient, getPatient, rememberPatient } from '../api/patients'
import type { Patient } from '../contracts/patient'
import { SectionCard } from '../components/SectionCard'
import { useWorkflow } from '../context/WorkflowContext'

function messageFor(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 403) return 'You are not authorized to access this patient.'
  if (error instanceof ApiError && error.status === 404) return 'Patient not found or not assigned to your workspace.'
  return error instanceof Error ? error.message : fallback
}

export function PatientsPage() {
  const { setWorkflow } = useWorkflow()
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
      const found = await getPatient(patientId.trim())
      rememberPatient(found)
      setPatient(found)
      setWorkflow({ patient_id: found.patient_id })
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
      rememberPatient(created)
      setPatient(created)
      setPatientId(created.patient_id)
      setWorkflow({ patient_id: created.patient_id })
      setDisplayName('')
      setCreatedMessage('Patient created and assigned to your workspace.')
    } catch (reason) {
      setError(messageFor(reason, 'Unable to create the patient.'))
    } finally {
      setIsLoading(false)
    }
  }

  return <div className="page-stack patients-page">
    <div className="dashboard-welcome"><div><p className="eyebrow">PATIENT ACCESS</p><h1>Patients</h1><p className="page-subtitle">Use the backend-issued patient ID to open an authorized patient record.</p></div></div>
    <div className="patients-workspace">
      <SectionCard title="Create patient" eyebrow="NEW RECORD" className="patients-card patients-create-card">
        <p className="patients-card-intro">Start a new authorized patient record.</p>
        <form onSubmit={create} className="patients-form create-patient-form">
          <label className="auth-field"><span>Patient display name</span><input value={displayName} onChange={(event) => setDisplayName(event.target.value)} minLength={2} maxLength={255} required /></label>
          <button className="primary-button patients-form-button" type="submit" disabled={isLoading}>{isLoading ? 'Saving…' : 'Create patient'}</button>
        </form>
      </SectionCard>
      <SectionCard title="Find patient" eyebrow="AUTHORIZED LOOKUP" className="patients-card patients-find-card">
        <p className="patients-card-intro">Use the backend-issued patient ID to open an authorized patient record.</p>
        <form onSubmit={lookup} className="patients-form find-patient-form">
          <label className="auth-field"><span>Patient ID</span><input value={patientId} onChange={(event) => setPatientId(event.target.value)} placeholder="Backend-issued UUID" required /></label>
          <button className="primary-button patients-form-button" type="submit" disabled={isLoading}>{isLoading ? 'Loading…' : 'Open patient'}</button>
        </form>
      </SectionCard>
    </div>
    {error && <p className="auth-status auth-error" role="alert">{error}</p>}
    {patient && <SectionCard title={patient.display_name || 'Patient record'} eyebrow="AUTHORIZED PATIENT" className="patient-result-card"><div className="patient-result-content"><div><p className="patients-card-intro" role="status">{createdMessage || 'This identity is issued and persisted by the backend.'}</p><p className="patient-result-detail">Ready to use for authorized lookup and upload.</p></div><div className="patient-id-display"><span>Patient ID</span><strong>{patient.patient_id}</strong></div></div></SectionCard>}
  </div>
}
