import { describe, expect, it } from 'vitest'
import step1Output from '../mocks/step1-output.json'
import type { Step1Output } from '../contracts/step1Output'
import { getConfidenceLabel, getConfidencePresentation } from '../lib/confidence'

describe('Step 1 fixture and confidence rules', () => {
  it('loads a contract-shaped Step1Output fixture', () => {
    const output: Step1Output = step1Output as unknown as Step1Output
    expect(output.extracted_fields.length).toBeGreaterThan(0)
    expect(output.extracted_fields[0]).toHaveProperty('field_id')
    expect(output.extracted_fields[0]).toHaveProperty('standardized_text')
  })

  it('keeps high-risk fields below 95% in review state', () => {
    const output = step1Output as unknown as Step1Output
    const field = output.extracted_fields.find((item) => item.is_high_risk_field && item.extraction_confidence < 0.95)
    expect(field).toBeDefined()
    expect(getConfidencePresentation(field!)).toBe('high-risk')
    expect(getConfidenceLabel(field!)).toBe('Doctor review required')
  })

  it('renders data-driven field types without a medication-specific branch', () => {
    const output = step1Output as unknown as Step1Output
    expect(output.extracted_fields.map((field) => field.field_type)).toEqual(['medication_name', 'medication_name', 'dosage_strength', 'frequency'])
  })
})
