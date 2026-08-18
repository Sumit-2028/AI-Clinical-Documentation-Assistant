import { Link } from 'react-router-dom'

export function AuthBrand() {
  return <Link to="/" className="auth-brand" aria-label="MedFlowAI home"><span className="auth-brand-mark">✦</span><span>MedFlow<span>AI</span></span></Link>
}
