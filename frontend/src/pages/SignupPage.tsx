import { AuthBrand } from '../components/AuthBrand'
import { SignupForm } from '../components/signup-form'

export function SignupPage() {
  return <div className="auth-page"><div className="auth-page-grid"><div className="auth-aside"><div><p className="marketing-eyebrow">A CLEARER CLINICAL START</p><h2>Bring the patient's story together.</h2><p>Set up a workspace designed for connected, traceable patient information and physician review.</p></div><div className="auth-aside-note"><span>＋</span><div><strong>Physician-controlled</strong><small>AI assists. You decide what belongs.</small></div></div></div><main className="auth-main"><AuthBrand /><SignupForm /></main></div></div>
}
