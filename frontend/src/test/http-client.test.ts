import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiClient, ApiError } from '../api/client'
import { login, logout } from '../api/auth'

const jsonResponse = (body: unknown, status = 200, headers: Record<string, string> = {}) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json', ...headers } })

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
  vi.resetModules()
  apiClient.setAccessToken(null)
  apiClient.setRefreshHandler(null)
  sessionStorage.clear()
})

describe('centralized HTTP transport', () => {
  it('adds the bearer token and parses JSON responses', async () => {
    apiClient.setAccessToken('access-token-for-test')
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ ok: true }))

    await expect(apiClient.get<{ ok: boolean }>('/api/v1/auth/me')).resolves.toEqual({ ok: true })
    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer access-token-for-test')
  })

  it('does not set a JSON content type for multipart requests', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ document_id: 'doc-1' }))
    const form = new FormData()
    form.append('patient_id', 'patient-1')
    form.append('file', new File(['clinical text'], 'note.txt', { type: 'text/plain' }))

    await apiClient.postForm('/api/v1/step1/documents/typed', form)
    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init?.headers).get('Content-Type')).toBeNull()
    expect(init?.body).toBe(form)
  })

  it('normalizes backend errors without exposing raw response internals', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ detail: [{ loc: ['body', 'email'], msg: 'Invalid email' }] }, 422, { 'x-request-id': 'trace-123' }))

    const error = await apiClient.get('/api/v1/auth/me').catch((reason) => reason)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 422, code: 'VALIDATION_ERROR', trace_id: 'trace-123' })
    expect(error.message).toBe('The request could not be completed.')
    expect(error.details).toEqual({ validation_errors: [{ loc: ['body', 'email'], msg: 'Invalid email' }] })
  })

  it('refreshes once after an unauthorized response and retries the original request', async () => {
    apiClient.setAccessToken('expired-access-token')
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ detail: 'Could not validate credentials.' }, 401))
      .mockResolvedValueOnce(jsonResponse({ ok: true }))
    const refresh = vi.fn().mockResolvedValue('fresh-access-token')
    apiClient.setRefreshHandler(refresh)

    await expect(apiClient.get<{ ok: boolean }>('/api/v1/step3/memory/patient-1/events')).resolves.toEqual({ ok: true })
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(new Headers(fetchMock.mock.calls[1][1]?.headers).get('Authorization')).toBe('Bearer fresh-access-token')
  })

  it('connects login to the auth contract and keeps the refresh token out of UI state', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ access_token: 'access-token', refresh_token: 'refresh-token', token_type: 'bearer' }))
      .mockResolvedValueOnce(jsonResponse({ id: 'user-1', email: 'doctor@example.com', full_name: 'Demo Physician', role: 'physician', is_active: true }))

    await expect(login({ email: 'doctor@example.com', password: 'password123' })).resolves.toMatchObject({ id: 'user-1', role: 'physician' })
    expect(sessionStorage.getItem('clinical-memory.refresh-token')).toBe('refresh-token')
    expect(document.body.textContent).not.toContain('access-token')
    logout()
    expect(sessionStorage.getItem('clinical-memory.refresh-token')).toBeNull()
  })

  it('maps typed upload to the authoritative multipart contract in the application runtime', async () => {
    vi.stubEnv('MODE', 'development')
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ document_id: 'document-1', processing_status: 'complete' }))
    const { uploadTypedDocument } = await import('../api/step1')
    const file = new File(['typed clinical note'], 'note.txt', { type: 'text/plain' })

    await expect(uploadTypedDocument({ patient_id: 'patient-1', encounter_id: 'encounter-1', modality: 'typed', file })).resolves.toMatchObject({ document_id: 'document-1', processing_status: 'complete' })
    const [, init] = fetchMock.mock.calls[0]
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/step1/documents/typed')
    expect(init?.body).toBeInstanceOf(FormData)
    expect((init?.body as FormData).get('patient_id')).toBe('patient-1')
    expect((init?.body as FormData).get('encounter_id')).toBe('encounter-1')
    expect((init?.body as FormData).get('file')).toMatchObject({ name: 'note.txt', type: 'text/plain' })
  })
})
