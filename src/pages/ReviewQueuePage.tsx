import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useReviewQueue } from '../hooks/useStep1'
import type { ExtractedField } from '../contracts/step1Output'
import { ConfidenceBadge, RiskBadge, StatusBadge } from '../components/Badges'
import { SectionCard } from '../components/SectionCard'
import { ArrowIcon, ChevronIcon, FileIcon, SearchIcon } from '../components/icons'

type Filter = 'All' | 'High Risk' | 'Review Required' | 'Handwritten' | 'Multilingual' | 'Medication' | 'Dosage' | 'Frequency' | 'Route'
const filters: Filter[] = ['All', 'High Risk', 'Review Required', 'Handwritten', 'Multilingual', 'Medication', 'Dosage', 'Frequency', 'Route']

export function ReviewQueuePage() {
  const { data, isLoading } = useReviewQueue()
  const [filter, setFilter] = useState<Filter>('All')
  const [search, setSearch] = useState('')
  const rows = useMemo(() => data?.flatMap((output) => output.extracted_fields.map((field) => ({ output, field }))) ?? [], [data])
  const reviewCount = rows.filter(({ field }) => field.requires_doctor_review_before_memory_write).length
  const visibleRows = rows.filter(({ output, field }) => {
    const currentValue = field.verified_text ?? field.standardized_text
    const text = `${field.field_type} ${field.raw_text} ${currentValue}`.toLowerCase()
    if (search && !text.includes(search.toLowerCase())) return false
    if (filter === 'High Risk') return field.is_high_risk_field
    if (filter === 'Review Required') return field.requires_doctor_review_before_memory_write
    if (filter === 'Handwritten' || filter === 'Multilingual') return output.input_modality === (filter === 'Handwritten' ? 'handwritten' : 'multilingual')
    if (['Medication', 'Dosage', 'Frequency', 'Route'].includes(filter)) return field.field_type.toLowerCase().includes(filter.toLowerCase())
    return true
  })

  return <div className="page-stack"><div className="page-heading"><div><p className="eyebrow">PHYSICIAN REVIEW</p><h1>Review queue</h1><p className="page-subtitle">Resolve uncertain information before it can be added to a patient record.</p></div><div className="queue-count"><strong>{reviewCount}</strong><span>items awaiting review</span></div></div><SectionCard title="Physician verification" eyebrow="INFORMATION NEEDING REVIEW" action={<div className="table-tools"><div className="search-box"><SearchIcon /><input aria-label="Search review queue" placeholder="Search information" value={search} onChange={(event) => setSearch(event.target.value)} /></div></div>}><div className="filter-row">{filters.map((item) => <button key={item} className={filter === item ? 'filter active' : 'filter'} onClick={() => setFilter(item)}>{item === 'Review Required' ? 'Needs review' : item}{item === 'Review Required' && <span>{reviewCount}</span>}</button>)}</div>{isLoading ? <div className="empty-loading">Loading review items…</div> : <div className="table-wrap"><table><thead><tr><th>Patient / document</th><th>Information</th><th>Original → standardized</th><th>Confidence</th><th>Risk</th><th>Review status</th><th /></tr></thead><tbody>{visibleRows.map(({ output, field }) => <ReviewRow key={field.field_id} output={output} field={field} />)}</tbody></table>{visibleRows.length === 0 && <div className="empty-loading">No items match this filter.</div>}</div>}</SectionCard></div>
}

function ReviewRow({ output, field }: { output: { patient_id: string; source_document: string; input_modality: 'typed' | 'handwritten' | 'multilingual'; created_at: string }; field: ExtractedField }) {
  const currentValue = field.verified_text ?? field.standardized_text
  return <tr><td><div className="patient-cell"><div className="mini-avatar">AM</div><div><strong>Ananya Mehta</strong><span>{output.patient_id} · {output.input_modality}</span><small><FileIcon /> {output.source_document}</small></div></div></td><td><span className="field-type">{field.field_type.replaceAll('_', ' ')}</span><span className="field-id">{field.field_id}</span></td><td><div className="text-pair"><span>{field.raw_text}</span><ArrowIcon /><strong>{currentValue}</strong></div></td><td><ConfidenceBadge field={field} /></td><td><RiskBadge highRisk={field.is_high_risk_field} /></td><td><div className="status-cell"><ReviewStatus status={field.review_status} /><small>{new Date(output.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</small></div></td><td><Link className="row-action" aria-label={`Review and correct ${field.field_id}`} to="/verification" state={{ fieldId: field.field_id }}><ChevronIcon /></Link></td></tr>
}

function ReviewStatus({ status }: { status: ExtractedField['review_status'] }) {
  if (status === 'approved') return <StatusBadge status="complete" />
  if (status === 'rejected') return <span className="status-badge status-failed"><span className="status-dot" />Rejected</span>
  return <StatusBadge status="pending_human_verification" />
}
