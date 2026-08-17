import { describe, expect, it } from 'vitest'
import { getStep1Output, getStep2Job, verifyStep1Field } from '../api'

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
    expect(output.extracted_fields.find((field) => field.field_id === 'fld_med_001')?.verified_text).toBe('Amoxicillin 500 mg')
  })

  it('returns the existing Step 2 response envelope', async () => {
    const response = await getStep2Job('job_nlp_412')
    expect(response).toHaveProperty('clinical_events')
    expect(response.clinical_events[0].event_local_id).toBe('evt_nlp_001')
    expect(response.patient_id).toBe('pat_00123')
  })
})
