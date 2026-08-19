import { fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { App } from '../App'
import { activateDemoSession, clearDemoSession } from '../lib/demoSession'

function renderApp(initialEntry = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[initialEntry]}><App /></MemoryRouter></QueryClientProvider>)
}

describe('shared physician workflow', () => {
  beforeEach(() => clearDemoSession())

  it('starts processing from upload and preserves patient, encounter, and document context', async () => {
    renderApp('/upload')
    expect(await screen.findByRole('heading', { name: 'Upload & process' })).toBeInTheDocument()
    expect(await screen.findByText('Document ready to process')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Start processing' }))
    expect(await screen.findByRole('heading', { name: 'Clinical intelligence' })).toBeInTheDocument()
    expect(screen.getByText('pat_00123')).toBeInTheDocument()
    expect(screen.queryByText('enc_2026_0817_01')).not.toBeInTheDocument()
    expect(screen.getByText('doc_5521')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Abbreviation review' })).toBeInTheDocument()
  })

  it('keeps only permanent destinations in the physician sidebar', () => {
    activateDemoSession()
    renderApp('/')
    const navigation = screen.getByRole('navigation')
    expect(within(navigation).getAllByRole('link')).toHaveLength(5)
    expect(within(navigation).getByRole('link', { name: 'Dashboard' })).toBeInTheDocument()
    expect(within(navigation).getByRole('link', { name: 'Patients' })).toBeInTheDocument()
    expect(within(navigation).getByRole('link', { name: /Review Queue/ })).toBeInTheDocument()
    expect(within(navigation).getByRole('link', { name: 'Upload & Process' })).toBeInTheDocument()
    expect(within(navigation).getByRole('link', { name: 'Patient Memory' })).toBeInTheDocument()
    expect(within(navigation).queryByRole('link', { name: /Clinical intelligence/i })).not.toBeInTheDocument()
    expect(within(navigation).queryByRole('link', { name: /conflict/i })).not.toBeInTheDocument()
  })

  it('keeps patient memory on the default tab with exactly four tabs', async () => {
    renderApp('/memory')
    const tablist = await screen.findByRole('tablist', { name: 'Patient memory views' })
    expect(within(tablist).getAllByRole('tab')).toHaveLength(4)
    expect(within(tablist).getByRole('tab', { name: 'Patient memory' })).toHaveAttribute('aria-selected', 'true')
    expect(within(tablist).getByRole('tab', { name: 'Patient timeline' })).toBeInTheDocument()
    expect(within(tablist).getByRole('tab', { name: 'Verified information' })).toBeInTheDocument()
    expect(within(tablist).getByRole('tab', { name: 'Unverified information' })).toBeInTheDocument()
    expect(within(tablist).queryByRole('tab', { name: /Clinical/i })).not.toBeInTheDocument()
    expect(await screen.findByText('Relevant patient context')).toBeInTheDocument()
    expect(screen.getByText('Recent patient activity')).toBeInTheDocument()
  })

  it('does not expose the memory handoff until review and safety are complete', async () => {
    renderApp('/clinical-nlp')
    expect(await screen.findByRole('heading', { name: 'Clinical intelligence' })).toBeInTheDocument()
    expect(await screen.findByText('Complete abbreviation review before clinical findings can be generated.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Open patient memory' })).not.toBeInTheDocument()

    for (const button of await screen.findAllByRole('button', { name: 'Use suggestion' })) fireEvent.click(button)
    expect(await screen.findByRole('button', { name: 'Open patient memory' })).toBeDisabled()
    const findings = screen.getByRole('heading', { name: 'Clinical findings' }).closest('section')!
    fireEvent.click(within(findings).getByRole('button', { name: 'Reject finding' }))
    const dialog = screen.getByRole('dialog', { name: 'Reject this finding?' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject finding' }))
    expect(await screen.findByRole('link', { name: 'Open patient memory' })).toHaveAttribute('href', '/memory')
    fireEvent.click(screen.getByRole('link', { name: 'Open patient memory' }))
    expect(await screen.findByRole('heading', { name: 'Ananya Mehta' })).toBeInTheDocument()
    expect(screen.getByDisplayValue('pat_00123')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('enc_2026_0817_01')).not.toBeInTheDocument()
  })
})
