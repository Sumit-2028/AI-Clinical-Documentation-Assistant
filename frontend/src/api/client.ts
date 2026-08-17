export interface ApiErrorPayload {
  code: string
  message: string
  details: Record<string, unknown>
  trace_id: string | null
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>
  readonly trace_id: string | null

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message)
    this.name = 'ApiError'
    this.status = status
    this.code = payload.code
    this.details = payload.details
    this.trace_id = payload.trace_id
  }
}

export type RefreshHandler = () => Promise<string | null>

interface RequestOptions {
  skipAuth?: boolean
  retryOnUnauthorized?: boolean
  timeoutMs?: number
}

const DEFAULT_TIMEOUT_MS = 30_000
const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

function normalizeBaseUrl(value: string): string {
  return value.replace(/\/$/, '')
}

function errorCode(status: number): string {
  if (status === 400) return 'BAD_REQUEST'
  if (status === 401) return 'UNAUTHORIZED'
  if (status === 403) return 'FORBIDDEN'
  if (status === 404) return 'NOT_FOUND'
  if (status === 409) return 'CONFLICT'
  if (status === 422) return 'VALIDATION_ERROR'
  if (status === 429) return 'RATE_LIMITED'
  if (status >= 500) return 'SERVER_ERROR'
  return 'HTTP_ERROR'
}

function asDetails(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function normalizeError(status: number, body: unknown, traceId: string | null): ApiErrorPayload {
  if (body && typeof body === 'object' && 'error' in body) {
    const error = (body as { error?: unknown }).error
    if (error && typeof error === 'object') {
      const value = error as Record<string, unknown>
      return {
        code: typeof value.code === 'string' ? value.code : errorCode(status),
        message: typeof value.message === 'string' ? value.message : 'The request could not be completed.',
        details: asDetails(value.details),
        trace_id: typeof value.trace_id === 'string' ? value.trace_id : traceId,
      }
    }
  }

  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail?: unknown }).detail
    return {
      code: errorCode(status),
      message: typeof detail === 'string' ? detail : 'The request could not be completed.',
      details: Array.isArray(detail) ? { validation_errors: detail } : {},
      trace_id: traceId,
    }
  }

  return {
    code: errorCode(status),
    message: 'The request could not be completed.',
    details: {},
    trace_id: traceId,
  }
}

async function readBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) return null
  try {
    return await response.json()
  } catch {
    return null
  }
}

class HttpClient {
  private accessToken: string | null = null
  private refreshHandler: RefreshHandler | null = null

  readonly baseUrl = normalizeBaseUrl(configuredBaseUrl)

  setAccessToken(token: string | null): void {
    this.accessToken = token
  }

  setRefreshHandler(handler: RefreshHandler | null): void {
    this.refreshHandler = handler
  }

  async request<T>(path: string, init: RequestInit = {}, options: RequestOptions = {}): Promise<T> {
    const controller = new AbortController()
    const timeout = window.setTimeout(
      () => controller.abort(),
      options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
    )
    const headers = new Headers(init.headers)
    if (this.accessToken && !options.skipAuth) headers.set('Authorization', `Bearer ${this.accessToken}`)
    if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }

    let response: Response
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        headers,
        signal: controller.signal,
      })
    } catch (error) {
      const message = error instanceof DOMException && error.name === 'AbortError'
        ? 'The request timed out.'
        : 'The backend could not be reached.'
      throw new ApiError(0, {
        code: error instanceof DOMException && error.name === 'AbortError' ? 'TIMEOUT' : 'NETWORK_ERROR',
        message,
        details: {},
        trace_id: null,
      })
    } finally {
      window.clearTimeout(timeout)
    }

    const traceId = response.headers.get('x-request-id')
    if (response.status === 401 && !options.skipAuth && options.retryOnUnauthorized !== false && this.refreshHandler) {
      const refreshed = await this.refreshHandler()
      if (refreshed) {
        this.accessToken = refreshed
        return this.request<T>(path, init, { ...options, retryOnUnauthorized: false })
      }
    }

    const body = await readBody(response)
    if (!response.ok) throw new ApiError(response.status, normalizeError(response.status, body, traceId))
    return body as T
  }

  get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { method: 'GET' }, options)
  }

  postJson<T>(path: string, payload: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    }, options)
  }

  postForm<T>(path: string, form: FormData, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { method: 'POST', body: form }, options)
  }
}

export const apiClient = new HttpClient()

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}
