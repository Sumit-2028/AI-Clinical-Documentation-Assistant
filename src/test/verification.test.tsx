import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { App } from '../App'
import step1Fixture from '../mocks/step1-output.json'

function renderVerification() { const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/verification']}><App /></MemoryRouter></QueryClientProvider>) }

describe('Step 1 physician correction', () => {
  it('opens the field selected from the Review Queue', async () => {
    const field = step1Fixture.extracted_fields.find((item) => item.field_id === 'fld_dose_001')!
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/review-queue']}><App /></MemoryRouter></QueryClientProvider>)
    fireEvent.click(await screen.findByRole('link', { name: `Review and correct ${field.field_id}` }))
    expect(await screen.findByRole('heading', { name: 'Review & correct extracted information' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Edit value', exact: true }))
    expect(screen.getByRole('textbox', { name: 'Physician correction' })).toHaveValue(field.standardized_text)
  })

  it('allows a physician to edit, preserve the original, and confirm a correction', async () => {
    const field = step1Fixture.extracted_fields.find((item) => item.requires_doctor_review_before_memory_write)!
    renderVerification()
    expect(await screen.findByRole('heading', { name: 'Review & correct extracted information' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Edit value', exact: true }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Physician correction' }), { target: { value: 'Amoxicillin 500 mg' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save correction' }))
    expect(screen.getByText('Physician corrected')).toBeInTheDocument()
    expect(screen.getAllByText(field.raw_text).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'Confirm and allow' }))
    expect(await screen.findByText('Review saved. Patient record access updated.')).toBeInTheDocument()
  })
})
