import { describe, expect, it } from 'vitest'
import { createPatient, getPatient, getReviewQueue, getSourceDocument, getStep1Output, getStep2Job, resolvePatient, searchPatients, verifyStep1Field } from '../api'

describe('Step 1 mock API', () => {
  it('returns typed Step1Output data', async () => {
    const output = await getStep1Output('job_ocr_771')
    expect(output.job_id).toBe('job_ocr_771')
    expect(output.extracted_fields[0].field_id).toBe('fld_med_001')
  })

  it('uses the contract verification payload and updates the field', async () => {
    const response = await verifyStep1Field({ field_id: 'fld_med_001', verified_text: 'Amoxicillin 500 mg', reviewer_id: 'phy_04', approved: true })
    expect(response).toMatchObject({ status: 'verified', audit_log_id: 'aud_9910' })
    const output = await getStep1Output('job_ocr_771')
    expect(output.extracted_fields.find((field) => field.field_id === 'fld_med_001')).toMatchObject({ verified_text: 'Amoxicillin 500 mg', standardized_text: 'Amoxicillin 500 mg', review_status: 'approved', requires_doctor_review_before_memory_write: false })
  })

  it('keeps rejected information out of memory and closes the queue only after review is complete', async () => {
    const rejected = await verifyStep1Field({ field_id: 'fld_dose_001', verified_text: '500 mg', reviewer_id: 'phy_04', approved: false })
    expect(rejected).toMatchObject({ status: 'rejected', written_to_memory: false })
    const afterReject = await getStep1Output('job_ocr_771')
    expect(afterReject).toMatchObject({ processing_status: 'pending_human_verification', written_to_memory: false })
    expect(afterReject.extracted_fields.find((field) => field.field_id === 'fld_dose_001')).toMatchObject({ review_status: 'rejected', verified_text: null, standardized_text: '500 mg', requires_doctor_review_before_memory_write: false })

    await verifyStep1Field({ field_id: 'fld_freq_001', verified_text: 'twice daily', reviewer_id: 'phy_04', approved: true })
    const completed = await getStep1Output('job_ocr_771')
    expect(completed).toMatchObject({ processing_status: 'complete', written_to_memory: false })
    expect(await getReviewQueue('pat_00123')).toEqual([])
  })

  it('returns the existing Step 2 response envelope', async () => {
    const response = await getStep2Job('job_nlp_412')
    expect(response).toHaveProperty('clinical_events')
    expect(response.clinical_events[0].event_local_id).toBe('evt_nlp_001')
    expect(response.patient_id).toBe('pat_00123')
  })

  it('resolves patients by ID and searches by patient name', async () => {
    expect(await getPatient('pat_00123')).toMatchObject({ patient_id: 'pat_00123', name: 'Ananya Mehta' })
    expect(await resolvePatient('pat_00123')).toMatchObject({ patient_id: 'pat_00123', name: 'Ananya Mehta' })
    expect((await searchPatients('Ananya')).map((patient) => patient.name)).toEqual(['Ananya Mehta', 'Ananya Malhotra'])
  })

  it('creates a Patient ID with linked ABHA and phone identifiers', async () => {
    const patient = await createPatient({ name: 'Riya Kapoor', abha_id: '98-7654-3210-9876', phone_number: '+91 9123456789' })

    expect(patient).toMatchObject({ name: 'Riya Kapoor', abha_id: '98765432109876', phone_number: '+919123456789' })
    expect(patient.patient_id).toMatch(/^pat_\d+$/)
    expect(await resolvePatient('98-7654-3210-9876')).toMatchObject({ patient_id: patient.patient_id })
    expect(await resolvePatient('9123456789')).toMatchObject({ patient_id: patient.patient_id })
    expect(await searchPatients('9123456789')).toEqual(expect.arrayContaining([expect.objectContaining({ patient_id: patient.patient_id })]))
  })

  it('rejects invalid or already-linked identifiers without overwriting associations', async () => {
    await expect(createPatient({ name: 'Invalid Patient', abha_id: '1234', phone_number: '9123456789' })).rejects.toMatchObject({ field: 'abha_id', code: 'invalid_format' })
    await expect(createPatient({ name: 'Invalid Patient', abha_id: '98-7654-3210-9877', phone_number: '12345' })).rejects.toMatchObject({ field: 'phone_number', code: 'invalid_format' })
    await expect(createPatient({ name: 'Duplicate Patient', abha_id: '98-7654-3210-9876', phone_number: '9987654321' })).rejects.toMatchObject({ field: 'abha_id', code: 'already_linked' })
    await expect(createPatient({ name: 'Duplicate Patient', abha_id: '87-6543-2109-8765', phone_number: '9123456789' })).rejects.toMatchObject({ field: 'phone_number', code: 'already_linked' })
  })

  it('resolves a clinical source document to a browser-openable stored file', async () => {
    const sourceDocument = await getSourceDocument('doc_5521')
    expect(sourceDocument).toMatchObject({ document_id: 'doc_5521', mime_type: 'application/pdf', storage_reference: 'clinical-documents/doc_5521/original.pdf' })
    expect(sourceDocument?.file_url).toMatch(/^data:application\/pdf;base64,/)
  })
})
