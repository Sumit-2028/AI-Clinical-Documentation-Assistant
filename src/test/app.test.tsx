import { fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { App } from '../App'

function renderApp(initialEntry = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[initialEntry]}><App /></MemoryRouter></QueryClientProvider>)
}

describe('MedFlow application', () => {
  it('renders the dashboard shell', async () => {
    renderApp()
    expect(await screen.findByText('Good morning, Dr. Mehta')).toBeInTheDocument()
    expect(screen.getByText('Recent uploads')).toBeInTheDocument()
  })

  it('renders the Step 1 upload route', async () => {
    renderApp('/upload')
    expect(await screen.findByRole('heading', { name: 'Upload & process' })).toBeInTheDocument()
    expect(screen.getByText('Multilingual')).toBeInTheDocument()
    expect(screen.getByText('Original language text is preserved')).toBeInTheDocument()
  })

  it('opens patient search without exposing encounter details', async () => {
    renderApp('/upload')
    await screen.findByRole('heading', { name: 'Upload & process' })

    fireEvent.click(screen.getByRole('button', { name: 'Selected patient' }))

    const menu = await screen.findByRole('listbox', { name: 'Patient results' })
    expect(within(menu).getByRole('searchbox', { name: 'Search patients' })).toBeInTheDocument()
    expect(await within(menu).findByRole('option', { name: /Ananya Mehta Patient ID pat_00123/ })).toBeInTheDocument()
    expect(within(menu).queryByText('Encounter ID')).not.toBeInTheDocument()
    expect(screen.queryByText('Encounter ID')).not.toBeInTheDocument()
  })

  it('renders the review queue route', async () => {
    renderApp('/review-queue')
    expect(await screen.findByRole('heading', { name: 'Review queue' })).toBeInTheDocument()
    expect(await screen.findByText('Amoxicillin')).toBeInTheDocument()
  })

  it('renders the aligned patient records workspace', async () => {
    renderApp('/patients')
    expect(await screen.findByRole('heading', { name: 'Patients' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Create patient' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Find patient' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Create patient/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Search patients/ })).toBeInTheDocument()
  })

  it('searches patients by name and opens the selected patient memory', async () => {
    renderApp('/patients')
    const search = await screen.findByRole('textbox', { name: 'Search patient' })
    fireEvent.change(search, { target: { value: 'Ananya' } })
    fireEvent.click(screen.getByRole('button', { name: /Search patients/ }))
    const results = await screen.findByRole('listbox', { name: 'Matching patients' })
    expect(within(results).getAllByRole('option')).toHaveLength(2)
    fireEvent.click(within(results).getByRole('option', { name: /Ananya Mehta Patient ID pat_00123/ }))
    expect(await screen.findByRole('heading', { name: 'Ananya Mehta' })).toBeInTheDocument()
    expect(screen.getByDisplayValue('pat_00123')).toBeInTheDocument()
    expect(screen.queryByText(/Encounter ID|enc_2026_0817_01/)).not.toBeInTheDocument()
  })

  it('routes the patient memory conflict review link to Resolve Conflict', async () => {
    renderApp('/memory')
    const input = await screen.findByRole('textbox', { name: "Ask about this patient's history" })
    fireEvent.change(input, { target: { value: 'What conflicts should I review?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }))
    const reviewLink = await screen.findByRole('link', { name: 'Review conflict' })
    expect(reviewLink).toHaveAttribute('href', '/resolve-conflict?patient_id=pat_00123&conflict_id=conflict_001')
    fireEvent.click(reviewLink)
    expect(await screen.findByRole('heading', { name: 'Resolve conflict' })).toBeInTheDocument()
    expect(screen.getByText('conflict_001')).toBeInTheDocument()
    expect(screen.getByText('No known drug allergies')).toBeInTheDocument()
    expect(screen.getByText('Penicillin allergy')).toBeInTheDocument()
  })

  it('records a conflict resolution and preserves the patient return link', async () => {
    renderApp('/resolve-conflict?patient_id=pat_00123&conflict_id=conflict_001')
    expect(await screen.findByRole('heading', { name: 'Resolve conflict' })).toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: 'Keep Record 1' }))
    expect(await screen.findByText('Conflict removed from active Needs Review.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Return to Patient Memory/ })).toHaveAttribute('href', '/memory?patient_id=pat_00123')
  })

  it('creates and opens a patient workspace after linking ABHA and phone', async () => {
    renderApp('/patients')
    fireEvent.change(await screen.findByRole('textbox', { name: 'Patient display name' }), { target: { value: 'Riya Kapoor' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'ABHA ID' }), { target: { value: '76-5432-1098-7654' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'Phone number' }), { target: { value: '+91 9234567890' } })
    fireEvent.click(screen.getByRole('button', { name: /Create patient/ }))

    expect(await screen.findByRole('heading', { name: 'Riya Kapoor' })).toBeInTheDocument()
    expect(screen.getByDisplayValue(/^pat_\d+$/)).toBeInTheDocument()
    expect(screen.queryByText(/76543210987654|9234567890/)).not.toBeInTheDocument()
  })

  it('shows clear validation feedback before creating a patient', async () => {
    renderApp('/patients')
    fireEvent.change(await screen.findByRole('textbox', { name: 'Patient display name' }), { target: { value: 'Invalid Patient' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'ABHA ID' }), { target: { value: '1234' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'Phone number' }), { target: { value: '12345' } })
    fireEvent.click(screen.getByRole('button', { name: /Create patient/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/valid 14-digit ABHA ID/)
    expect(screen.getByRole('heading', { name: 'Create patient' })).toBeInTheDocument()
  })

  it('renders the audit log route', async () => {
    renderApp('/audit-log')
    expect(await screen.findByRole('heading', { name: 'Audit log' })).toBeInTheDocument()
    expect(await screen.findByText('doc_5521')).toBeInTheDocument()
  })
})
