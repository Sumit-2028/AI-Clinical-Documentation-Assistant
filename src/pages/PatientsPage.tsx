import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { createPatient, normalizeAbhaId, normalizePhoneNumber, PatientValidationError, resolvePatient, searchPatients } from '../api'
import { ArrowIcon } from '../components/icons'
import { SectionCard } from '../components/SectionCard'
import { useWorkflow } from '../context/WorkflowContext'
import type { PatientRecord } from '../contracts/patient'

export function PatientsPage() {
  const navigate = useNavigate()
  const { workflow, setWorkflow } = useWorkflow()
  const [patientName, setPatientName] = useState('')
  const [abhaId, setAbhaId] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [patientSearch, setPatientSearch] = useState('')
  const [matches, setMatches] = useState<PatientRecord[]>([])
  const [isCreating, setIsCreating] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [createError, setCreateError] = useState('')
  const [searchMessage, setSearchMessage] = useState('')

  const openPatient = (patient: PatientRecord) => {
    const nextWorkflow = { ...workflow, patient_id: patient.patient_id, encounter_id: patient.encounter_id, current_stage: 'patient-memory' as const }
    setWorkflow(nextWorkflow)
    navigate('/memory', { state: { workflow: nextWorkflow, patient } })
  }

  const handleCreatePatient = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setCreateError('')
    setIsCreating(true)
    try {
      const patient = await createPatient({ name: patientName, abha_id: abhaId, phone_number: phoneNumber })
      setPatientName('')
      setAbhaId('')
      setPhoneNumber('')
      openPatient(patient)
    } catch (error) {
      setCreateError(error instanceof PatientValidationError ? error.message : 'The patient record could not be created. Try again.')
    } finally {
      setIsCreating(false)
    }
  }

  const findPatient = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const query = patientSearch.trim()
    if (!query) {
      setSearchMessage('Enter a patient ID or name to continue.')
      setMatches([])
      return
    }
    setIsSearching(true)
    setSearchMessage('')
    const directMatch = await resolvePatient(query)
    const isDirectIdentifier = /^pat_/i.test(query) || Boolean(normalizeAbhaId(query)) || Boolean(normalizePhoneNumber(query))
    if (isDirectIdentifier && directMatch) {
      openPatient(directMatch)
      return
    }
    const results = await searchPatients(query)
    setMatches(results)
    setIsSearching(false)
    setSearchMessage(results.length === 0 ? 'No patients found.' : `${results.length} matching ${results.length === 1 ? 'patient' : 'patients'} found.`)
  }

  return <div className="page-stack patients-page">
    <div className="page-heading patients-heading">
      <div><p className="eyebrow">PATIENT RECORDS</p><h1>Patients</h1><p className="page-subtitle">Create a new patient record or find an existing patient.</p></div>
    </div>

    <div className="patients-action-grid">
      <SectionCard title="Create patient" eyebrow="NEW RECORD" className="patient-action-card">
        <p className="patient-form-hint">A Patient ID is generated automatically and remains the primary identifier. ABHA ID and phone number are securely linked for verification and retrieval.</p>
        <form className="patient-create-form" onSubmit={handleCreatePatient}>
          <label className="patient-form-field">Patient display name<input aria-label="Patient display name" value={patientName} onChange={(event) => setPatientName(event.target.value)} placeholder="Enter patient name" /></label>
          <label className="patient-form-field">ABHA ID<input aria-label="ABHA ID" value={abhaId} onChange={(event) => setAbhaId(event.target.value)} placeholder="12-3456-7890-1234" autoComplete="off" /></label>
          <label className="patient-form-field">Registered phone number<input aria-label="Phone number" type="tel" inputMode="tel" value={phoneNumber} onChange={(event) => setPhoneNumber(event.target.value)} placeholder="+91 9876543210" autoComplete="off" /></label>
          <button className="primary-button patient-create-button" type="submit" disabled={isCreating}>{isCreating ? 'Creating patient…' : 'Create patient'} <ArrowIcon /></button>
        </form>
        {createError && <p className="patient-form-message patient-form-error" role="alert">{createError}</p>}
      </SectionCard>
      <div className="page-heading patients-heading">
        <div><h1>Access Patient's Memory</h1></div>
      </div>

      <SectionCard title="Find patient" eyebrow="RETURNING PATIENT" className="patient-action-card">
        <form className="patient-find-form" onSubmit={findPatient}>
          <label className="patient-form-field">Patient ID, name, ABHA ID, or phone<input aria-label="Search patient" value={patientSearch} onChange={(event) => { setPatientSearch(event.target.value); setMatches([]); setSearchMessage('') }} placeholder="Patient ID, name, ABHA ID, or phone" /></label>
          <button className="secondary-button patient-find-button" type="submit" disabled={isSearching}>{isSearching ? 'Searching…' : 'Search patients'} <ArrowIcon /></button>
        </form>
        {searchMessage && <p className="patient-form-message" role="status">{searchMessage}</p>}
        {matches.length > 0 && <div className="patient-results" role="listbox" aria-label="Matching patients">{matches.map((patient) => <button key={patient.patient_id} type="button" role="option" className="patient-result" onClick={() => openPatient(patient)}><span className="patient-initials">{patient.name.split(' ').map((part) => part[0]).join('').slice(0, 2)}</span><span className="patient-option-copy"><strong>{patient.name}</strong><small>Patient ID {patient.patient_id} · {patient.age} years · {patient.gender}</small></span><ArrowIcon /></button>)}</div>}
      </SectionCard>
    </div>
  </div>
}
