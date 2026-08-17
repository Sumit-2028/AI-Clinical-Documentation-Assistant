import type { ReactNode } from 'react'
import type { ExtractedField } from '../contracts/step1Output'
import { formatConfidence, getConfidenceLabel, getConfidencePresentation } from '../lib/confidence'

export function StatusBadge({ status }: { status: 'complete' | 'pending_human_verification' | 'failed' }) {
  const label = status === 'complete' ? 'Complete' : status === 'failed' ? 'Processing failed' : 'Physician review required'
  return <span className={`status-badge status-${status}`}><span className="status-dot" />{label}</span>
}

export function ConfidenceBadge({ field }: { field: ExtractedField }) {
  const presentation = getConfidencePresentation(field)
  return <span className={`confidence-badge confidence-${presentation}`}><span>{formatConfidence(field.extraction_confidence)}</span>{getConfidenceLabel(field)}</span>
}

export function TrustTierBadge({ tier, children }: { tier: 1 | 2 | 3; children?: ReactNode }) {
  const label = children ?? (tier === 1 ? 'Verified record' : tier === 2 ? 'Physician-approved' : 'Unverified information')
  return <span className={`tier-badge tier-${tier}`}>{label}</span>
}

export function RiskBadge({ highRisk }: { highRisk: boolean }) { return highRisk ? <span className="risk-badge risk-high">High risk</span> : <span className="risk-badge risk-info">Standard field</span> }
