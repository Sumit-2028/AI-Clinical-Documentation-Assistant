import { fireEvent, render, screen, within } from '@testing-library/react'
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
const valid = response.clinical_events.find((event) => event.validation_status === 'valid')!
const reviewRequiredCount = response.clinical_events.filter((event) => event.validation_status !== 'valid').length
const eligibleReviewRequired = { ...valid, event_local_id: 'evt_review_eligible', normalized_concept: 'Reviewable eligible finding', gemini_contextualization_confidence: 0.79, ambiguous_abbreviation_resolved: { ...valid.ambiguous_abbreviation_resolved, was_ambiguous: false, resolved_value: null } }
const eligibleReviewResponse = { ...response, clinical_events: [eligibleReviewRequired] }

function renderCard(event: ClinicalEvent) { return render(<ClinicalEventCard event={event} onProvenance={() => undefined} />) }
function renderApp(seed?: Step2Response) { const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); if (seed) { client.setQueryData(['step2-clinical-nlp'], seed); client.setQueryData(['step2-process'], seed) }; return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/clinical-nlp']}><App /></MemoryRouter></QueryClientProvider>) }

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
    expect(screen.getByText('Suggested interpretation: twice daily')).toBeInTheDocument()
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

  it('shows all decisions for a review-required finding that remains safety-eligible', () => {
    render(<ClinicalEventCard event={eligibleReviewRequired} onProvenance={() => undefined} onApprove={() => undefined} onReject={() => undefined} onEditInterpretation={() => undefined} />)
    expect(screen.getByText('Review required')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit interpretation' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reject finding' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add to patient record' })).toBeEnabled()
    expect(screen.queryByText('This finding cannot be added to the patient record')).not.toBeInTheDocument()
  })

  it('renders the data-driven NLP page and provenance drawer', async () => {
    renderApp()
    expect(await screen.findByRole('heading', { name: 'Clinical intelligence' })).toBeInTheDocument()
    expect(await screen.findByText('Complete abbreviation review before clinical findings can be generated.')).toBeInTheDocument()
    expect(screen.queryByText(valid.event_local_id)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'View all clinical findings' })).not.toBeInTheDocument()
    for (const button of await screen.findAllByRole('button', { name: 'Use suggestion' })) fireEvent.click(button)
    expect(await screen.findByRole('button', { name: 'View all clinical findings' })).toBeInTheDocument()
    expect(screen.getByText('Ready to add to patient record')).toBeInTheDocument()
    expect(await screen.findByText(`${reviewRequiredCount} ${reviewRequiredCount === 1 ? 'finding needs' : 'findings need'} your review`)).toBeInTheDocument()
    expect(screen.getByText('Show source text')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View all clinical findings' })).toBeInTheDocument()
    const findingsSection = screen.getByRole('heading', { name: 'Clinical findings' }).closest('section')!
    expect(within(findingsSection).queryByText(valid.event_local_id)).not.toBeInTheDocument()
    expect(within(findingsSection).getByRole('button', { name: 'Reject finding' })).toBeInTheDocument()
    expect(within(findingsSection).queryByRole('button', { name: 'Add to patient record' })).not.toBeInTheDocument()
    fireEvent.click(within(findingsSection).getByRole('button', { name: 'Reject finding' }))
    const rejectDialog = screen.getByRole('dialog', { name: 'Reject this finding?' })
    fireEvent.click(within(rejectDialog).getByRole('button', { name: 'Reject finding' }))
    expect(await screen.findByText(reviewRequiredCount === 1 ? 'No findings require your review' : `${reviewRequiredCount - 1} ${reviewRequiredCount === 2 ? 'finding needs' : 'findings need'} your review`)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'View all clinical findings' }))
    expect(screen.getByText('Hide additional findings')).toBeInTheDocument()
    expect(await screen.findByText('Rejected')).toBeInTheDocument()
    expect(within(findingsSection).getByText(valid.event_local_id)).toBeInTheDocument()
    const invalidCard = screen.getByText(invalid.normalized_concept).closest('article')!
    expect(within(invalidCard).queryByRole('button', { name: 'Add to patient record' })).not.toBeInTheDocument()
    expect(within(invalidCard).getByText('This finding cannot be added to the patient record')).toBeInTheDocument()
    const addButton = within(findingsSection).getAllByRole('button', { name: 'Add to patient record' })[0]
    expect(addButton).toBeEnabled()
    fireEvent.click(addButton)
    const addDialog = screen.getByRole('dialog', { name: 'Add this finding to the patient record?' })
    fireEvent.click(within(addDialog).getByRole('button', { name: 'Add to patient record' }))
    expect(await screen.findByText('Added to patient record')).toBeInTheDocument()
    expect((await screen.findAllByText('No history of diabetes')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('This finding cannot be added to the patient record')).length).toBeGreaterThan(0)
    render(<ProvenanceDrawer event={medication} onClose={() => undefined} />)
    expect(screen.getByRole('dialog', { name: 'Source information' })).toBeInTheDocument()
    expect(screen.getByText('Source text')).toBeInTheDocument()
    expect(screen.getByText('Start')).toBeInTheDocument()
  })

  it('allows a physician to use or edit an ambiguous interpretation without changing the source', async () => {
    renderApp()
    expect(await screen.findByRole('heading', { name: 'Clinical intelligence' })).toBeInTheDocument()
    expect(await screen.findByText('Complete abbreviation review before clinical findings can be generated.')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: 'Edit interpretation' })[0])
    const dialog = screen.getByRole('dialog', { name: 'Correct abbreviation' })
    fireEvent.change(within(dialog).getByRole('textbox', { name: 'Interpretation' }), { target: { value: 'Once daily' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save correction' }))
    expect(await screen.findByText('Physician corrected')).toBeInTheDocument()
    expect(screen.getAllByText('Once daily').length).toBeGreaterThan(0)
    expect(screen.getAllByText(medication.original_text).length).toBeGreaterThan(0)
  })

  it('confirms an eligible review-required add and updates the review count without removing the event', async () => {
    renderApp(eligibleReviewResponse)
    expect(await screen.findByText('1 finding needs your review')).toBeInTheDocument()
    expect(screen.getAllByText('Reviewable eligible finding').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'Add to patient record' }))
    const dialog = screen.getByRole('dialog', { name: 'Add this finding to the patient record?' })
    expect(screen.getByText("This finding has passed the current safety checks and can be added to the patient's clinical record.")).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Add to patient record' }))
    expect(await screen.findByText('Added to patient record')).toBeInTheDocument()
    expect(await screen.findByText('No findings require your review')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'View all clinical findings' }))
    expect(screen.getAllByText('Reviewable eligible finding').length).toBeGreaterThan(0)
  })
})
