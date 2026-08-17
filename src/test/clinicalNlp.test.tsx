import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import clinicalNlpFixture from '../mocks/clinical-events.json'
import type { ClinicalEvent, Step2Response } from '../contracts/clinicalEvent'
import { ClinicalEventCard } from '../components/ClinicalEventCard'
import { ProvenanceDrawer } from '../components/ProvenanceDrawer'
import { App } from '../App'

const response = clinicalNlpFixture as unknown as Step2Response
const medication = response.clinical_events.find((event) => event.entity_type === 'Medication')!
const lab = response.clinical_events.find((event) => event.entity_type === 'LabFinding')!
const invalid = response.clinical_events.find((event) => event.validation_status !== 'valid')!

function renderCard(event: ClinicalEvent) { return render(<ClinicalEventCard event={event} onProvenance={() => undefined} />) }
function renderApp() { const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/clinical-nlp']}><App /></MemoryRouter></QueryClientProvider>) }

describe('Clinical NLP experience', () => {
  it('renders medication event details, confidence, relationships, and attributes', () => {
    renderCard(medication)
    expect(screen.getByText('Metformin')).toBeInTheDocument()
    expect(screen.getByText('evt_nlp_001')).toBeInTheDocument()
    expect(screen.getByText('affirmed')).toBeInTheDocument()
    expect(screen.getByText(/SNOMED CT/)).toBeInTheDocument()
    expect(screen.getByText('109081006')).toBeInTheDocument()
    expect(screen.getByText('has dosage')).toBeInTheDocument()
    expect(screen.getByText('twice daily')).toBeInTheDocument()
    expect(screen.getByText('Resolved: twice daily')).toBeInTheDocument()
  })

  it('renders lab attributes and temporal context', () => {
    renderCard(lab)
    expect(screen.getByText('Laboratory finding', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('specific date')).toBeInTheDocument()
    expect(screen.getByText('HbA1c')).toBeInTheDocument()
    expect(screen.getByText('7.2')).toBeInTheDocument()
    expect(screen.getByText('%')).toBeInTheDocument()
  })

  it('blocks invalid validation output from the memory-ready state', () => {
    renderCard(invalid)
    expect(screen.getByText('This finding cannot be added to the patient record')).toBeInTheDocument()
    expect(screen.getByText('Review required')).toBeInTheDocument()
  })

  it('renders the data-driven NLP page and provenance drawer', async () => {
    renderApp()
    expect(await screen.findByRole('heading', { name: 'Clinical intelligence' })).toBeInTheDocument()
    expect(screen.getByText('Ready to add to patient record')).toBeInTheDocument()
    expect((await screen.findAllByText('No history of diabetes')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('This finding cannot be added to the patient record')).length).toBeGreaterThan(0)
    render(<ProvenanceDrawer event={medication} onClose={() => undefined} />)
    expect(screen.getByRole('dialog', { name: 'Source information' })).toBeInTheDocument()
    expect(screen.getByText('Source text')).toBeInTheDocument()
    expect(screen.getByText('Start')).toBeInTheDocument()
  })
})
