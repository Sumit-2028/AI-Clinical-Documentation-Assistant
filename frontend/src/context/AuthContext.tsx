import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { clearAuthTokens, getCurrentUser, login as loginRequest, logout as logoutRequest, refreshAccessToken } from '../api/auth'
import type { AuthUser } from '../contracts/auth'

interface AuthContextValue {
  user: AuthUser | null
  isLoading: boolean
  isAuthenticated: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)
const isTestRuntime = import.meta.env.MODE === 'test'
const isDevelopmentBypass = import.meta.env.DEV && import.meta.env.VITE_AUTH_BYPASS !== 'false'
const isLocalAuthBypass = isTestRuntime || isDevelopmentBypass
const testUser: AuthUser = {
  id: 'test-user',
  email: 'doctor@example.com',
  full_name: 'Demo Physician',
  role: 'physician',
  is_active: true,
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(isLocalAuthBypass ? testUser : null)
  const [isLoading, setIsLoading] = useState(!isLocalAuthBypass)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isLocalAuthBypass) return
    let cancelled = false
    void (async () => {
      try {
        const accessToken = await refreshAccessToken()
        if (!accessToken) return
        const currentUser = await getCurrentUser()
        if (!cancelled) setUser(currentUser)
      } catch {
        clearAuthTokens()
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  const value = useMemo<AuthContextValue>(() => ({
    user,
    isLoading,
    isAuthenticated: Boolean(user?.is_active),
    error,
    login: async (email, password) => {
      setError(null)
      try {
        const currentUser = isLocalAuthBypass ? testUser : await loginRequest({ email, password })
        setUser(currentUser)
      } catch (reason) {
        const message = reason instanceof Error ? reason.message : 'Unable to sign in.'
        setError(message)
        throw reason
      }
    },
    logout: () => {
      logoutRequest()
      setUser(isLocalAuthBypass ? testUser : null)
    },
  }), [error, isLoading, user])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (value) return value
  if (isLocalAuthBypass) {
    return {
      user: testUser,
      isLoading: false,
      isAuthenticated: true,
      error: null,
      login: async () => undefined,
      logout: () => undefined,
    }
  }
  throw new Error('useAuth must be used inside AuthProvider')
}
