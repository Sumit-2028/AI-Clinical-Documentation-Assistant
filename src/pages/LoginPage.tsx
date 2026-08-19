import { AuthBrand } from '../components/AuthBrand'
import { LoginForm } from '../components/login-form'

export function LoginPage() {
  return <div className="auth-page"><div className="auth-page-grid"><div className="auth-aside"><div><p className="marketing-eyebrow">MEDFLOWAI / CLINICAL INTELLIGENCE</p><h2>Keep the physician in the loop.</h2><p>Connected history should make today's decision clearer, without taking the decision away from you.</p></div><div className="auth-aside-note"><span>✦</span><div><strong>Traceable by design</strong><small>Every relevant fact keeps its source.</small></div></div></div><main className="auth-main"><AuthBrand /><LoginForm /></main></div></div>
}
