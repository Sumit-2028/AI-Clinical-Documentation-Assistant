import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { AlertIcon, CheckIcon } from '../components/icons'
import { useAuth } from '../context/AuthContext'

export function LoginPage() {
  const { isAuthenticated, isLoading, error, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (!isLoading && isAuthenticated) return <Navigate to={(location.state as { from?: string } | null)?.from ?? '/'} replace />

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)
    try {
      await login(email, password)
      navigate((location.state as { from?: string } | null)?.from ?? '/', { replace: true })
    } catch {
      // AuthContext exposes the normalized message for the form; avoid an unhandled promise in the UI.
    } finally {
      setSubmitting(false)
    }
  }

  return <main className="login-shell"><section className="login-card"><div className="brand"><div className="brand-mark"><CheckIcon /></div><div><div className="brand-name">MedFlow<span>AI</span></div><div className="brand-caption">Clinical intelligence</div></div></div><p className="eyebrow">SECURE WORKSPACE</p><h1>Sign in</h1><p className="page-subtitle">Use your clinical workspace credentials to continue.</p><form onSubmit={submit}><label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required /></label>{error && <p className="error-copy"><AlertIcon />{error}</p>}<button className="primary-button" type="submit" disabled={submitting || isLoading}>{submitting ? 'Signing in…' : 'Sign in'}</button></form></section></main>
}
