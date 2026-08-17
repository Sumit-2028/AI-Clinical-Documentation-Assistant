import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { App } from '../App'
import { generateDocument, finalizeDocument, listDocuments } from '../api'
import clinicalEvents from '../mocks/clinical-events.json'
import retrievedContext from '../mocks/retrieved-context.json'
import type { ClinicalEvent, Step2Response } from '../contracts/clinicalEvent'
import type { DocumentGenerationRequest, GeneratedDocument } from '../contracts/documents'
import type { RetrievedContext } from '../contracts/retrievedContext'
import { DocumentEditor } from '../components/DocumentEditor'
import { DocumentReviewFlags } from '../components/DocumentReviewFlags'

const consultation = clinicalEvents as unknown as Step2Response
const context = retrievedContext as unknown as RetrievedContext
const request: DocumentGenerationRequest = { patient_id: 'pat_00123', encounter_id: 'enc_2026_0817_01', document_type: 'soap_note', current_consultation_events: consultation.clinical_events, retrieved_context: context, physician_instructions: null }
const renderApp = (entry = '/documentation') => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[entry]}><App /></MemoryRouter></QueryClientProvider>)

describe('Step 4 documentation generation', () => {
  it('uses the exact generation and finalization contracts', async () => {
    const document = await generateDocument(request)
    expect(document).toMatchObject({ document_id: 'doc_soap_001', document_type: 'soap_note', status: 'draft' })
    expect(document.sections.subjective).toBeTruthy()
    expect(document.flags_for_physician_review[0]).toHaveProperty('source_provenance')
    expect(document.provenance_map.some((entry) => entry.trust_tier === 3)).toBe(true)
    expect(document.validation_result).toMatchObject({ passed: true, auto_regeneration_attempts: 0 })
    const finalized = await finalizeDocument(document.document_id, { action: 'accept', physician_id: 'phy_04', edited_sections: null, regenerate_notes: null })
    expect(finalized.status).toBe('finalized')
    if (finalized.status === 'finalized') {
      expect(finalized.memory_write_payload.source).toBe('physician_approved_consultation')
      expect(finalized.memory_write_payload.clinical_events.every((event) => event.validation_status === 'valid')).toBe(true)
    }
  })

  it('renders the generation form and complete structured draft review flow', async () => {
    renderApp()
    expect(await screen.findByRole('heading', { name: 'Documentation workspace' })).toBeInTheDocument()
    expect(screen.getByText('Create clinical document')).toBeInTheDocument()
    expect(screen.getByText('Current consultation')).toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: /Create clinical draft/ }))
    expect(await screen.findByRole('heading', { name: 'SOAP Note' })).toBeInTheDocument()
    expect(screen.getByText('Items requiring physician review')).toBeInTheDocument()
    expect(screen.getByText('Unverified information')).toBeInTheDocument()
    expect(screen.getByText('Potential conflict between no known drug allergies and a Tier 3 reported penicillin allergy.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /View source information/ }))
    expect(screen.getByRole('dialog', { name: 'Source and verification' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close source and verification' }))
    fireEvent.click(screen.getByRole('button', { name: /Edit sections/ }))
    const subjective = screen.getByRole('textbox', { name: 'Subjective' })
    fireEvent.change(subjective, { target: { value: 'Edited physician subjective assessment.' } })
    fireEvent.click(screen.getByRole('button', { name: /Save edits & finalize/ }))
    expect((await screen.findAllByText('Approved clinical information')).length).toBeGreaterThan(0)
    expect((screen.getAllByText(/Findings/)).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: /Add to patient record/ }))
    expect(await screen.findByText(/records added/)).toBeInTheDocument()
  })

  it('renders discharge sections dynamically and keeps history separate', async () => {
    const dischargeRequest = { ...request, document_type: 'discharge_summary' as const }
    const discharge = await generateDocument(dischargeRequest)
    expect(discharge.sections.patient_identification).toContain('pat_00123')
    expect(discharge.sections.subjective).toBeNull()
    const documents = await listDocuments()
    expect(documents.some((item) => item.document_type === 'discharge_summary')).toBe(true)
    renderApp('/documents')
    expect(await screen.findByRole('heading', { name: 'Clinical documents' })).toBeInTheDocument()
    expect((await screen.findAllByText('Document history')).length).toBeGreaterThan(0)
    expect(await screen.findByText('Discharge summary')).toBeInTheDocument()
  })

  it('keeps section editing structured and renders review flag details', () => {
    const document = { sections: { subjective: 'S', objective: null, assessment: 'A', plan: 'P', patient_identification: null, reason_for_encounter: null, medications: null, allergies: null, procedures: null, relevant_history: null, follow_up: null } } as GeneratedDocument
    const event = consultation.clinical_events.find((item) => item.validation_status === 'valid') as ClinicalEvent
    expect(event.normalized_concept).toBeTruthy()
    render(<DocumentEditor sections={document.sections} editedSections={{}} editable onChange={() => undefined} />)
    expect(screen.getByRole('textbox', { name: 'Subjective' })).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Objective' })).not.toBeInTheDocument()
    const flag = { type: 'conflict', conflict_id: 'conflict_001', risk_level: 'high' as const, description: 'Review allergy conflict', source_provenance: { fact_id: 'fact_1', trust_tier: 3 as const, source_document_id: 'doc_1', original_text: 'Penicillin allergy', source_language: 'en', input_modality: 'typed', extraction_confidence: 0.74 } }
    render(<DocumentReviewFlags flags={[flag]} onProvenance={() => undefined} />)
    expect(screen.getByText('Review allergy conflict')).toBeInTheDocument()
    expect(screen.getByText('High safety priority')).toBeInTheDocument()
  })
})
