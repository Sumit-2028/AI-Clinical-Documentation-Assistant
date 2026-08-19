import type { CreatePatientInput, PatientRecord, PatientValidationField } from '../contracts/patient'
import patientFixtures from '../mocks/patients.json'

const patients = [...(patientFixtures as PatientRecord[])]
const pause = (milliseconds = 120): Promise<void> => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

export type PatientValidationCode = 'required' | 'invalid_format' | 'already_linked'

export class PatientValidationError extends Error {
  constructor(
    public readonly field: PatientValidationField,
    public readonly code: PatientValidationCode,
    message: string,
  ) {
    super(message)
    this.name = 'PatientValidationError'
  }
}

export function normalizeAbhaId(value: string): string | null {
  const compact = value.trim().replace(/[\s-]/g, '')
  return /^\d{14}$/.test(compact) ? compact : null
}

export function normalizePhoneNumber(value: string): string | null {
  const compact = value.trim().replace(/[\s()-]/g, '')
  if (/^[6-9]\d{9}$/.test(compact)) return `+91${compact}`
  if (/^\+91[6-9]\d{9}$/.test(compact)) return compact
  if (/^91[6-9]\d{9}$/.test(compact)) return `+${compact}`
  return null
}

function nextPatientId(): string {
  const lastSequence = patients.reduce((highest, patient) => {
    const sequence = Number(patient.patient_id.match(/^pat_(\d+)$/i)?.[1] ?? 0)
    return Number.isFinite(sequence) ? Math.max(highest, sequence) : highest
  }, 0)
  return `pat_${String(lastSequence + 1).padStart(5, '0')}`
}

export async function searchPatients(query: string): Promise<PatientRecord[]> {
  await pause()
  const normalized = query.trim().toLowerCase()
  if (!normalized) return patients
  const compactQuery = normalized.replace(/[\s-]/g, '')
  return patients.filter((patient) => patient.patient_id.toLowerCase().includes(normalized) || patient.name.toLowerCase().includes(normalized) || patient.abha_id.includes(compactQuery) || patient.phone_number.replace('+', '').includes(compactQuery))
}

export async function getPatient(patientId: string): Promise<PatientRecord | null> {
  await pause()
  return patients.find((patient) => patient.patient_id.toLowerCase() === patientId.trim().toLowerCase()) ?? null
}

export async function resolvePatient(identifier: string): Promise<PatientRecord | null> {
  const normalized = identifier.trim().toLowerCase()
  if (!normalized) return null
  const exactId = patients.find((patient) => patient.patient_id.toLowerCase() === normalized)
  if (exactId) return exactId
  const normalizedAbha = normalizeAbhaId(identifier)
  const exactAbha = normalizedAbha ? patients.find((patient) => patient.abha_id === normalizedAbha) : null
  if (exactAbha) return exactAbha
  const normalizedPhone = normalizePhoneNumber(identifier)
  const exactPhone = normalizedPhone ? patients.find((patient) => patient.phone_number === normalizedPhone) : null
  if (exactPhone) return exactPhone
  const exactNameMatches = patients.filter((patient) => patient.name.toLowerCase() === normalized)
  return exactNameMatches.length === 1 ? exactNameMatches[0] : null
}

export async function createPatient(input: CreatePatientInput): Promise<PatientRecord> {
  await pause()

  const name = input.name.trim()
  if (!name) throw new PatientValidationError('name', 'required', 'Enter a patient name to continue.')

  const abhaId = normalizeAbhaId(input.abha_id)
  if (!abhaId) throw new PatientValidationError('abha_id', 'invalid_format', 'Enter a valid 14-digit ABHA ID, for example 12-3456-7890-1234.')
  if (patients.some((patient) => patient.abha_id === abhaId)) throw new PatientValidationError('abha_id', 'already_linked', 'This ABHA ID is already linked to another Patient ID.')

  const phoneNumber = normalizePhoneNumber(input.phone_number)
  if (!phoneNumber) throw new PatientValidationError('phone_number', 'invalid_format', 'Enter a valid Indian mobile number beginning with 6, 7, 8, or 9.')
  if (patients.some((patient) => patient.phone_number === phoneNumber)) throw new PatientValidationError('phone_number', 'already_linked', 'This phone number is already linked to another Patient ID.')

  const patientId = nextPatientId()
  const patient: PatientRecord = {
    patient_id: patientId,
    name,
    age: input.age ?? 0,
    gender: input.gender?.trim() || 'Not specified',
    status: 'active',
    encounter_id: `enc_${patientId}`,
    existing_context_summary: 'No historical context yet',
    abha_id: abhaId,
    phone_number: phoneNumber,
  }
  patients.push(patient)
  return patient
}
