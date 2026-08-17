import { fireEvent, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import memoryEvents from '../mocks/memory-events.json'
import retrievedContext from '../mocks/retrieved-context.json'
import { getConflictList, getMemoryEvents, resolveConflict, approveTier3, rejectTier3, retrieveMemory } from '../api'
import type { MemoryFact } from '../contracts/memory'
import type { RetrievedContext } from '../contracts/retrievedContext'
import { MemoryFactCard } from '../components/MemoryFactCard'
import { MemoryProvenanceDrawer } from '../components/MemoryProvenanceDrawer'
import { deriveQueryConcepts, MemoryExplorerPage } from '../pages/MemoryExplorerPage'

const context = retrievedContext as unknown as RetrievedContext
const timeline = memoryEvents as unknown as MemoryFact[]
const renderWithQuery = (ui: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>)

describe('Step 3 memory contracts and views', () => {
  it('keeps verified, unverified, trust tiers, and high-risk conflict facts distinct', async () => {
    const result = await retrieveMemory({ patient_id: 'pat_00123', encounter_id: 'enc_2026_0817_01', query_concepts: ['allergy'] })
    expect(result.verified_context.conditions[0].trust_tier).toBe(1)
    expect(result.verified_context.medications[0].trust_tier).toBe(2)
    expect(result.unverified_information[0].trust_tier).toBe(3)
    expect(result.conflicts[0]).toMatchObject({ conflict_id: 'conflict_001', risk_level: 'high', status: 'unresolved' })
    expect(result.conflicts[0].event_a).toHaveProperty('source_text_span.start')
    expect(result.conflicts[0].event_b).toHaveProperty('contextualization_confidence')
  })

  it('renders MemoryFact contract fields, medication attributes, confidence, and tier actions', () => {
    const fact = context.unverified_information.find((item) => item.entity_type === 'Medication')!
    const onApprove = (value: MemoryFact) => expect(value.event_id).toBe(fact.event_id)
    render(<MemoryFactCard fact={fact} onProvenance={() => undefined} onApprove={onApprove} onReject={() => undefined} />)
    expect(screen.getByText(fact.normalized_concept)).toBeInTheDocument()
    expect(screen.getByText(fact.snomed_ct_id!)).toBeInTheDocument()
    expect(screen.getByText(fact.assertion)).toBeInTheDocument()
    expect(screen.getByText(fact.clinical_status)).toBeInTheDocument()
    expect(screen.getByText(fact.temporal_context)).toBeInTheDocument()
    expect(screen.getByText(/1000 mg/)).toBeInTheDocument()
    expect(screen.getByText('Unverified information')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Approve/ }))
  })

  it('renders append-only medication changes as separate timeline events', async () => {
    renderWithQuery(<MemoryRouter><MemoryExplorerPage initialView="timeline" /></MemoryRouter>)
    expect((await screen.findAllByText(/500 mg/)).length).toBeGreaterThan(0)
    expect((await screen.findAllByText(/1000 mg/)).length).toBeGreaterThan(0)
    expect((await screen.findAllByText(/discontinued/)).length).toBeGreaterThan(0)
    expect(screen.getByText(/No records overwritten/)).toBeInTheDocument()
    expect(screen.getByText(/500 mg.*1000 mg.*discontinued/)).toBeInTheDocument()
  })

  it('supports natural-language clinical questions and suggested follow-ups', async () => {
    expect(deriveQueryConcepts('What medication changes are relevant to chest pain?')).toEqual(expect.arrayContaining(['chest pain', 'medications', 'medication changes']))
    renderWithQuery(<MemoryRouter><MemoryExplorerPage /></MemoryRouter>)
    const input = await screen.findByRole('textbox', { name: "Ask about this patient's history" })
    fireEvent.change(input, { target: { value: 'What medications is this patient currently taking?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(screen.getByText('What medications is this patient currently taking?')).toBeInTheDocument()
    expect(await screen.findByText('Here is the relevant clinical context.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Recent medication changes' }))
    expect(screen.getAllByText('Recent medication changes').length).toBeGreaterThan(0)
    expect(await screen.findByText('Relevant medication history')).toBeInTheDocument()
  })

  it('links contextual conflicts with the current patient and encounter', async () => {
    renderWithQuery(<MemoryRouter><MemoryExplorerPage /></MemoryRouter>)
    const input = await screen.findByRole('textbox', { name: "Ask about this patient's history" })
    fireEvent.change(input, { target: { value: 'What conflicts should I review?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }))
    const reviewLink = await screen.findByRole('link', { name: 'Review conflict' })
    expect(reviewLink).toHaveAttribute('href', '/conflicts?patient_id=pat_00123&encounter_id=enc_2026_0817_01')
  })

  it('opens the existing conflict workflow with patient context populated', async () => {
    renderWithQuery(<MemoryRouter initialEntries={['/conflicts?patient_id=pat_00999&encounter_id=enc_context_01']}><MemoryExplorerPage initialView="conflicts" /></MemoryRouter>)
    expect(await screen.findByDisplayValue('pat_00999')).toBeInTheDocument()
    expect(screen.getByDisplayValue('enc_context_01')).toBeInTheDocument()
    expect(await screen.findByText('Conflicting records')).toBeInTheDocument()
  })

  it('renders provenance source span and confidence fields', () => {
    const fact = context.verified_context.lab_trends[0]
    render(<MemoryProvenanceDrawer fact={fact} onClose={() => undefined} />)
    expect(screen.getByText(fact.source_document_id)).toBeInTheDocument()
    expect(screen.getByText(String(fact.source_text_span.start))).toBeInTheDocument()
    expect(screen.getByText(String(fact.source_text_span.end))).toBeInTheDocument()
    expect(screen.getByText(fact.input_modality)).toBeInTheDocument()
    expect(screen.getByText(fact.source_language.toUpperCase())).toBeInTheDocument()
    expect(screen.getByText(/Translation confidence/)).toBeInTheDocument()
    expect(screen.getByText('Clinical interpretation')).toBeInTheDocument()
  })

  it('renders conflict center actions without choosing an event automatically', async () => {
    renderWithQuery(<MemoryRouter><MemoryExplorerPage initialView="conflicts" /></MemoryRouter>)
    expect(await screen.findByText('No known drug allergies')).toBeInTheDocument()
    expect(screen.getByText('Penicillin allergy')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm record 1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm record 2' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Keep unresolved' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Keep unresolved' }))
    expect(screen.getByText('Decision recorded')).toBeInTheDocument()
  })

  it('uses exact conflict resolution and Tier 3 review payloads', async () => {
    const conflicts = await getConflictList('pat_00123')
    expect(await resolveConflict(conflicts[0].conflict_id, { resolution_action: 'confirm_event_b', physician_id: 'phy_04' })).toEqual({ conflict_id: 'conflict_001', status: 'resolved', new_event_id: 'mem_evt_resolution_001' })
    expect(await approveTier3('mem_evt_unverified_001', 'phy_04')).toMatchObject({ event_id: 'mem_evt_unverified_001', new_trust_tier: 2 })
    expect(await rejectTier3('mem_evt_unverified_001', 'phy_04')).toEqual({ event_id: 'mem_evt_unverified_001', trust_tier: 3, reviewed_status: 'reviewed_rejected' })
    expect((await getMemoryEvents('pat_00123')).map((event) => event.medication_attributes.dosage)).toEqual(['500 mg', '1000 mg', null])
  })
})
