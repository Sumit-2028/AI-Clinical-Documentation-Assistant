import type { DocumentSections } from '../contracts/documents'

export const documentSectionLabels: Record<keyof DocumentSections, string> = {
  subjective: 'Subjective', objective: 'Objective', assessment: 'Assessment', plan: 'Plan',
  patient_identification: 'Patient identification', reason_for_encounter: 'Reason for encounter',
  medications: 'Medications', allergies: 'Allergies', procedures: 'Procedures',
  relevant_history: 'Relevant history', follow_up: 'Follow-up',
}

export function DocumentEditor({ sections, editedSections, editable, onChange }: { sections: DocumentSections; editedSections: Partial<DocumentSections>; editable: boolean; onChange: (key: keyof DocumentSections, value: string) => void }) {
  const keys = (Object.keys(documentSectionLabels) as Array<keyof DocumentSections>).filter((key) => sections[key] !== null)
  return <div className="document-section-list">{keys.map((key) => {
    const value = editedSections[key] ?? sections[key] ?? ''
    return <article className={`document-section ${editable ? 'document-section-editing' : ''}`} key={key}><div className="document-section-heading"><span>{documentSectionLabels[key]}</span><span className="structured-label">Structured section</span></div>{editable ? <textarea aria-label={documentSectionLabels[key]} value={value} onChange={(event) => onChange(key, event.target.value)} /> : <p>{value}</p>}</article>
  })}</div>
}
