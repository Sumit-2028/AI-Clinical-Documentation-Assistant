const DEMO_SESSION_KEY = 'medflow.demo-session'

function getSessionStorage(): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

export function isDemoSessionActive(): boolean {
  return getSessionStorage()?.getItem(DEMO_SESSION_KEY) === 'active'
}

export function activateDemoSession(): void {
  getSessionStorage()?.setItem(DEMO_SESSION_KEY, 'active')
}

export function clearDemoSession(): void {
  getSessionStorage()?.removeItem(DEMO_SESSION_KEY)
}
