import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { App } from '../App'

function renderApp(initialEntry = '/') {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('MedFlow application', () => {
  it('renders the public landing page', async () => {
    renderApp()

    expect(
      await screen.findByRole('heading', {
        name: "A patient's history is more than a document.",
      }),
    ).toBeInTheDocument()

    expect(
      screen.getByText('MedFlow connects the pieces.'),
    ).toBeInTheDocument()
  })

  it('renders the dashboard shell on the authenticated dashboard route', async () => {
    renderApp('/dashboard')

    expect(
      await screen.findByText('Good morning, Dr. Mehta'),
    ).toBeInTheDocument()

    expect(
      screen.getByText('Recent uploads'),
    ).toBeInTheDocument()
  })

  it('renders the Step 1 upload route', async () => {
    renderApp('/upload')

    expect(
      await screen.findByRole('heading', {
        name: 'Upload & process',
      }),
    ).toBeInTheDocument()

    expect(
      screen.getByText('Multilingual'),
    ).toBeInTheDocument()

    expect(
      screen.getByText('Original language text is preserved'),
    ).toBeInTheDocument()
  })

  it('renders the review queue route', async () => {
    renderApp('/review-queue')

    expect(
      await screen.findByRole('heading', {
        name: 'Review queue',
      }),
    ).toBeInTheDocument()

    expect(
      await screen.findByText('Amoxicillin'),
    ).toBeInTheDocument()
  })

  it('renders the audit log route', async () => {
    renderApp('/audit-log')

    expect(
      await screen.findByRole('heading', {
        name: 'Audit log',
      }),
    ).toBeInTheDocument()

    expect(
      await screen.findByText('doc_5521'),
    ).toBeInTheDocument()
  })
})