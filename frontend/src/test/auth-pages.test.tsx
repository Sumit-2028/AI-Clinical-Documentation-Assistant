import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { App } from '../App'

afterEach(() => vi.restoreAllMocks())

function renderAppAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}><App /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('authentication pages', () => {
  it('connects registration to the backend and returns to login', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        id: 'user-1',
        email: 'new@example.com',
        full_name: 'New Physician',
        role: 'physician',
        is_active: true,
      }), { status: 201, headers: { 'Content-Type': 'application/json' } }),
    ))
    const user = userEvent.setup()
    renderAppAt('/signup')

    await user.type(screen.getByLabelText('Full Name'), 'New Physician')
    await user.type(screen.getByLabelText('Email'), 'new@example.com')
    await user.type(screen.getByLabelText('Password', { selector: 'input' }), 'password123')
    await user.type(screen.getByLabelText('Confirm Password'), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByRole('heading', { name: 'Welcome back to MedFlowAI' })).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/v1/auth/register'), expect.objectContaining({ method: 'POST' }))
  })

  it('shows duplicate-account errors from the backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'An account with this email already exists.' }), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      }),
    ))
    const user = userEvent.setup()
    renderAppAt('/signup')

    await user.type(screen.getByLabelText('Full Name'), 'Existing Physician')
    await user.type(screen.getByLabelText('Email'), 'existing@example.com')
    await user.type(screen.getByLabelText('Password', { selector: 'input' }), 'password123')
    await user.type(screen.getByLabelText('Confirm Password'), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent('An account with this email already exists.')
  })

  it('navigates a valid login to the protected dashboard in test runtime', async () => {
    const user = userEvent.setup()
    renderAppAt('/login')

    await user.type(screen.getByLabelText('Email'), 'doctor@example.com')
    await user.type(screen.getByLabelText('Password Forgot your password?'), 'password123')
    await user.click(screen.getByRole('button', { name: /^login/i }))

    expect(await screen.findByText('Recent uploads')).toBeInTheDocument()
  })

  it('prevents submission when passwords differ', async () => {
    const user = userEvent.setup()
    renderAppAt('/signup')
    await user.type(screen.getByLabelText('Full Name'), 'New Physician')
    await user.type(screen.getByLabelText('Email'), 'new@example.com')
    await user.type(screen.getByLabelText('Password', { selector: 'input' }), 'password123')
    await user.type(screen.getByLabelText('Confirm Password'), 'different123')
    await user.click(screen.getByRole('button', { name: /create account/i }))
    expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match.')
  })
})
