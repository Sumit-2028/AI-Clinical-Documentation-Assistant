import { useEffect, useState } from 'react'
import { getSourceDocument } from '../api'
import type { SourceDocument } from '../contracts/sourceDocument'
import { ArrowIcon, FileIcon } from './icons'

interface SourceDocumentLinkProps {
  documentId?: string | null
  className?: string
  label?: string
  showDocument?: boolean
  showAction?: boolean
}

export function SourceDocumentLink({ documentId, className = '', label = 'Open source record', showDocument = true, showAction = true }: SourceDocumentLinkProps) {
  const [sourceDocument, setSourceDocument] = useState<SourceDocument | null>(null)
  const [loading, setLoading] = useState(Boolean(documentId))

  useEffect(() => {
    let active = true
    if (!documentId) {
      setSourceDocument(null)
      setLoading(false)
      return () => { active = false }
    }
    setLoading(true)
    void getSourceDocument(documentId).then((document) => {
      if (!active) return
      setSourceDocument(document)
      setLoading(false)
    })
    return () => { active = false }
  }, [documentId])

  if (loading) return <span className={`source-document-status ${className}`}><FileIcon /><span>{documentId}</span><small>Retrieving attached source…</small></span>
  if (!sourceDocument) return <span className={`source-document-status source-document-error ${className}`}><FileIcon /> {documentId ?? 'Source record not linked'}</span>

  return <a className={`source-document-link ${className}`} href={sourceDocument.file_url} target="_blank" rel="noreferrer" aria-label={`Open source document ${sourceDocument.document_id}`}>{showDocument && <><FileIcon /><span>{sourceDocument.document_id}</span><small>{sourceDocument.file_name}</small></>}{showAction && <strong className="source-document-open-label">{label} <ArrowIcon /></strong>}</a>
}
