import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { activateDemoSession } from '../lib/demoSession'

const DEMO_EMAIL = 'admin@gmail.com'
const DEMO_PASSWORD = '1234'

export function LoginForm() {
  const navigate = useNavigate()
  const location = useLocation()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const registered = (location.state as { registered?: boolean } | null)?.registered

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email') ?? '').trim()
    const password = String(form.get('password') ?? '')
    setFormError(null)
    setIsSubmitting(true)

    if (email !== DEMO_EMAIL || password !== DEMO_PASSWORD) {
      setFormError('Invalid email or password.')
      setIsSubmitting(false)
      return
    }

    activateDemoSession()
    navigate('/', { replace: true })
  }

  return <div className="auth-form-wrap">
    <div className="auth-card">
      <div className="auth-card-header"><p className="auth-kicker">PHYSICIAN WORKSPACE</p><h1>Welcome back to MedFlowAI</h1><p>Sign in to your physician workspace.</p></div>
      <form onSubmit={handleSubmit}>
        <div className="auth-socials"><button className="auth-social" type="button" disabled title="Social sign-in is not configured"><span className="social-glyph">A</span> Login with Apple</button><button className="auth-social" type="button" disabled title="Social sign-in is not configured"><span className="social-glyph google">G</span> Login with Google</button></div>
        <div className="auth-separator"><span>Or continue with email</span></div>
        <label className="auth-field"><span>Email</span><input id="login-email" name="email" type="email" placeholder="doctor@clinic.org" autoComplete="email" required /></label>
        <label className="auth-field"><span>Password <span className="auth-inline-muted">Forgot your password?</span></span><input id="login-password" name="password" type="password" autoComplete="current-password" required /></label>
        <button className="auth-submit" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Signing in...' : <>Login <span>→</span></>}</button>
        {formError && <p className="auth-status auth-error" role="alert">{formError}</p>}
        {registered && <p className="auth-status" role="status">Demo workspace ready. Use admin@gmail.com and 1234.</p>}
      </form>
      <p className="auth-switch">Don't have an account? <Link to="/signup">Sign up</Link></p>
    </div>
    <p className="auth-legal">By continuing, you agree to use MedFlowAI as a physician-controlled clinical workspace.</p>
  </div>
}
