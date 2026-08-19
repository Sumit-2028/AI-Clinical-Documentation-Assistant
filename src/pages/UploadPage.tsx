import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { searchPatients, uploadHandwrittenDocument, uploadMultilingualInput, uploadTypedDocument } from '../api'
import type { InputModality, ProcessingStatus } from '../contracts/common'
import type { Step1Output } from '../contracts/step1Output'
import type { PatientRecord } from '../contracts/patient'
import { useStep1Output } from '../hooks/useStep1'
import { useWorkflow } from '../context/WorkflowContext'
import { AlertIcon, ArrowIcon, CheckIcon, FileIcon, SearchIcon, UploadIcon } from '../components/icons'
import { StatusBadge } from '../components/Badges'
import { SectionCard } from '../components/SectionCard'
import { WorkflowProgress } from '../components/WorkflowProgress'

export function UploadPage() {
  const navigate = useNavigate()
  const { data: output } = useStep1Output()
  const { workflow, beginProcessing } = useWorkflow()
  const [modality, setModality] = useState<InputModality>('multilingual')
  const [fileName, setFileName] = useState(output?.source_document ?? '')
  const [patientId, setPatientId] = useState(output?.patient_id ?? workflow.patient_id)
  const [encounterId] = useState(output?.encounter_id ?? workflow.encounter_id)
  const [sourceLanguage, setSourceLanguage] = useState(output?.source_language ?? 'hi')
  const [isDragging, setIsDragging] = useState(false)
  const [patientMenuOpen, setPatientMenuOpen] = useState(false)
  const [patientSearch, setPatientSearch] = useState('')
  const [patientResults, setPatientResults] = useState<PatientRecord[]>([])
  const patientSelectorRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  const upload = useMutation({
    mutationFn: async () => {
      const request = { patient_id: patientId, encounter_id: encounterId, modality, source_language: modality === 'multilingual' ? sourceLanguage : 'en' }
      return modality === 'typed' ? uploadTypedDocument(request) : modality === 'handwritten' ? uploadHandwrittenDocument(request) : uploadMultilingualInput(request)
    },
    onSuccess: (response) => {
      void queryClient.invalidateQueries({ queryKey: ['step1-output'] })
      const nextWorkflow = beginProcessing({ patient_id: patientId, encounter_id: encounterId, document_id: response.document_id, processing_status: response.processing_status })
      navigate('/clinical-nlp', { state: { workflow: nextWorkflow } })
    },
  })

  const currentStatus: ProcessingStatus = output?.processing_status ?? 'pending_human_verification'
  useEffect(() => {
    if (output && !fileName) setFileName(output.source_document)
  }, [output, fileName])
  useEffect(() => {
    if (!patientMenuOpen) return
    const handlePointerDown = (event: PointerEvent) => {
      if (patientSelectorRef.current && !patientSelectorRef.current.contains(event.target as Node)) setPatientMenuOpen(false)
    }
    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [patientMenuOpen])
  useEffect(() => {
    if (!patientMenuOpen) return
    let active = true
    void searchPatients(patientSearch).then((results) => { if (active) setPatientResults(results) })
    return () => { active = false }
  }, [patientMenuOpen, patientSearch])

  const handleFile = (file: File | undefined) => {
    if (file) setFileName(file.name)
  }
  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    handleFile(event.dataTransfer.files[0])
  }
  const handleBrowse = (event: ChangeEvent<HTMLInputElement>) => handleFile(event.target.files?.[0])

  return <div className="page-stack">
    <div className="page-heading">
      <div><p className="eyebrow">INPUT PROCESSING</p><h1>Upload &amp; process</h1><p className="page-subtitle">Bring clinical information into the patient record with a confidence check.</p></div>
      <div className="heading-meta"><span className="live-dot" /> Processing system ready</div>
    </div>

    <WorkflowProgress />

    <div className="upload-grid">
      <SectionCard title="Source document" eyebrow="01 / INPUT" className="source-card">
        <div className={`dropzone ${isDragging ? 'dragging' : ''}`} onDragEnter={() => setIsDragging(true)} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setIsDragging(false)} onDrop={handleDrop}>
          <div className="upload-symbol"><UploadIcon /></div>
          <h3>{fileName ? 'Document ready to process' : 'Drop a clinical document here'}</h3>
          <p>PDF, PNG or JPG · up to 25 MB</p>
          <label className="secondary-button browse-button">Browse files<input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={handleBrowse} /></label>
        </div>
        {fileName && <div className="file-preview"><div className="file-icon"><FileIcon /></div><div><strong>{fileName}</strong><span>{modality === 'multilingual' ? 'Multilingual document' : `${modality[0].toUpperCase()}${modality.slice(1)} document`}</span></div><span className="file-ready"><CheckIcon /> Ready</span></div>}
        <div className="form-divider" />
        <div className="form-grid">
          <div className="patient-field">
            <span className="field-label">Patient search / select</span>
            <div className={`patient-selector ${patientMenuOpen ? 'is-open' : ''}`} ref={patientSelectorRef}>
              <button type="button" className="input-with-icon patient-selector-trigger" aria-haspopup="listbox" aria-expanded={patientMenuOpen} aria-label="Selected patient" onClick={() => setPatientMenuOpen((open) => !open)} onKeyDown={(event) => { if (event.key === 'Escape') { setPatientMenuOpen(false); event.currentTarget.blur() } }}>
                <span className="patient-initials">AM</span><span className="patient-selector-name">Ananya Mehta</span><span className="select-caret" aria-hidden="true">⌄</span>
              </button>
              {patientMenuOpen && <div className="patient-selector-menu" role="listbox" aria-label="Patient results" onClick={(event) => event.stopPropagation()}>
                <div className="patient-search-input"><SearchIcon /><input autoFocus type="search" aria-label="Search patients" placeholder="Search by patient ID or name" value={patientSearch} onChange={(event) => setPatientSearch(event.target.value)} onKeyDown={(event) => { if (event.key === 'Escape') setPatientMenuOpen(false) }} /></div>
                {patientResults.length > 0 ? patientResults.map((patient) => <button key={patient.patient_id} type="button" role="option" aria-selected={patient.patient_id === patientId} className="patient-option" onClick={() => { setPatientId(patient.patient_id); setPatientMenuOpen(false); setPatientSearch('') }}><span className="patient-initials">{patient.name.split(' ').map((part) => part[0]).join('').slice(0, 2)}</span><span className="patient-option-copy"><strong>{patient.name}</strong><small>Patient ID {patient.patient_id}</small></span>{patient.patient_id === patientId ? <CheckIcon /> : <ArrowIcon />}</button>) : <p className="patient-empty">No patients found.</p>}
              </div>}
            </div>
          </div>
          <label>Patient ID<input value={patientId} onChange={(event) => setPatientId(event.target.value)} /></label>
        </div>
      </SectionCard>

      <SectionCard title="Document type" eyebrow="02 / ROUTING" className="modality-card">
        <p className="card-intro">Choose the document type so MedFlow can apply the right review safeguards.</p>
        <div className="modality-options">{(['typed', 'handwritten', 'multilingual'] as InputModality[]).map((item) => <button key={item} className={`modality-option ${modality === item ? 'selected' : ''}`} onClick={() => setModality(item)}><span className="radio-indicator" /><span><strong>{item[0].toUpperCase() + item.slice(1)}</strong><small>{item === 'typed' ? 'Standard text document' : item === 'handwritten' ? 'Handwritten document with additional review' : 'Document in another language with translation'}</small></span></button>)}</div>
        {modality === 'multilingual' && <div className="language-panel"><div><label>Source language</label><select value={sourceLanguage} onChange={(event) => setSourceLanguage(event.target.value)}><option value="hi">Hindi</option><option value="ta">Tamil</option><option value="en">English</option></select></div><div><label>Translation confidence</label><div className="read-only-value">{output ? `${Math.round((output.translation_confidence ?? 0) * 100)}%` : '—'}</div></div><div className="original-text"><span>Original language text is preserved</span><p>{output?.original_language_text ?? 'Original text will appear here after extraction.'}</p></div></div>}
        <div className="route-note"><span className="route-note-icon"><CheckIcon /></span><span><strong>Processing method selected</strong><small>{modality === 'typed' ? 'Typed documents use standard text processing.' : 'This document will receive additional confidence review.'}</small></span></div>
        <button className="primary-button process-button" onClick={() => upload.mutate()} disabled={upload.isPending || !fileName}>{upload.isPending ? 'Starting processing…' : 'Start processing'}<ArrowIcon /></button>
        {upload.isError && <p className="error-copy"><AlertIcon /> Unable to start processing. Try again.</p>}
      </SectionCard>
    </div>

    {output && <ExtractionSnapshot output={output} status={currentStatus} />}
  </div>
}

function ExtractionSnapshot({ output, status }: { output: Step1Output; status: ProcessingStatus }) {
  const reviewCount = useMemo(() => output.extracted_fields.filter((field) => field.requires_doctor_review_before_memory_write).length, [output])
  return <SectionCard title="Latest processing result" eyebrow="03 / PROCESSING STATUS" action={<div className="snapshot-actions"><StatusBadge status={status} />{reviewCount > 0 && <a className="text-link" href="/verification">Review &amp; correct <ArrowIcon /></a>}</div>}><div className="job-summary"><div><span>Document</span><strong>{output.source_document}</strong></div><div><span>Processing record</span><strong>{output.job_id}</strong></div><div><span>Information extracted</span><strong>{output.extracted_fields.length}</strong></div><div><span>Needs review</span><strong className="review-number">{reviewCount}</strong></div></div></SectionCard>
}
