import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

export function SignupForm() {
  const [submitted, setSubmitted] = useState(false)
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setSubmitted(true) }
  return <div className="auth-form-wrap">
    <div className="auth-card">
      <div className="auth-card-header"><p className="auth-kicker">PHYSICIAN WORKSPACE</p><h1>Create your MedFlowAI account</h1><p>Set up your physician workspace.</p></div>
      <form onSubmit={handleSubmit}>
        <label className="auth-field"><span>Full Name</span><input id="signup-name" name="name" type="text" placeholder="Dr. Riya Mehta" autoComplete="name" required /></label>
        <label className="auth-field"><span>Email</span><input id="signup-email" name="email" type="email" placeholder="doctor@clinic.org" autoComplete="email" required /></label>
        <div className="auth-field-grid"><label className="auth-field"><span>Password</span><input id="signup-password" name="password" type="password" autoComplete="new-password" minLength={8} required /></label><label className="auth-field"><span>Confirm Password</span><input id="confirm-password" name="confirm-password" type="password" autoComplete="new-password" minLength={8} required /></label></div>
        <p className="auth-help">Must be at least 8 characters long.</p>
        <button className="auth-submit" type="submit">Create Account <span>→</span></button>
        {submitted && <p className="auth-status" role="status">Account creation is ready to connect to your existing sign-up service.</p>}
      </form>
      <p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p>
    </div>
    <p className="auth-legal">By continuing, you agree to use MedFlowAI as a physician-controlled clinical workspace.</p>
  </div>
}
