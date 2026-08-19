export type SourceDocumentMimeType = 'application/pdf' | 'image/jpeg' | 'image/png' | 'text/plain'

export interface SourceDocument {
  document_id: string
  file_name: string
  mime_type: SourceDocumentMimeType
  file_url: string
  storage_provider: string
  storage_reference: string
}
