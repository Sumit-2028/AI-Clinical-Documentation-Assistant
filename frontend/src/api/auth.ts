import type { AuthUser, LoginRequest, RefreshTokenRequest, RegisterRequest, TokenResponse } from '../contracts/auth'
import { apiClient } from './client'

const REFRESH_TOKEN_KEY = 'clinical-memory.refresh-token'
let refreshInFlight: Promise<string | null> | null = null

function getStoredRefreshToken(): string | null {
  try {
    return window.sessionStorage.getItem(REFRESH_TOKEN_KEY)
  } catch {
    return null
  }
}

function storeTokens(tokens: TokenResponse): void {
  apiClient.setAccessToken(tokens.access_token)
  try {
    window.sessionStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
  } catch {
    // A session-storage failure should not put tokens into UI state or logs.
  }
}

export function clearAuthTokens(): void {
  apiClient.setAccessToken(null)
  try {
    window.sessionStorage.removeItem(REFRESH_TOKEN_KEY)
  } catch {
    // Best effort cleanup for restricted browser storage.
  }
}

export async function login(request: LoginRequest): Promise<AuthUser> {
  const tokens = await apiClient.postJson<TokenResponse>('/api/v1/auth/login', request, { skipAuth: true, retryOnUnauthorized: false })
  storeTokens(tokens)
  try {
    return await getCurrentUser()
  } catch (error) {
    clearAuthTokens()
    throw error
  }
}

export function register(request: RegisterRequest): Promise<AuthUser> {
  return apiClient.postJson<AuthUser>('/api/v1/auth/register', request, {
    skipAuth: true,
    retryOnUnauthorized: false,
  })
}

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = refreshAccessTokenInternal()
  try {
    return await refreshInFlight
  } finally {
    refreshInFlight = null
  }
}

async function refreshAccessTokenInternal(): Promise<string | null> {
  const refresh_token = getStoredRefreshToken()
  if (!refresh_token) return null
  const request: RefreshTokenRequest = { refresh_token }
  try {
    const tokens = await apiClient.postJson<TokenResponse>('/api/v1/auth/refresh', request, { skipAuth: true, retryOnUnauthorized: false })
    storeTokens(tokens)
    return tokens.access_token
  } catch {
    clearAuthTokens()
    return null
  }
}

apiClient.setRefreshHandler(refreshAccessToken)

export function getCurrentUser(): Promise<AuthUser> {
  return apiClient.get<AuthUser>('/api/v1/auth/me')
}

export function logout(): void {
  clearAuthTokens()
}
