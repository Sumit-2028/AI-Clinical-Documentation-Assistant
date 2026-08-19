import type { SourceDocument } from '../contracts/sourceDocument'

const pause = (milliseconds = 120): Promise<void> => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

// In production this resource comes from the document-storage service. The mock keeps
// the same contract: document ID -> storage reference -> browser-openable file URL.
const makeMockTextDocument = (documentId: string, fileName: string, content: string): SourceDocument => ({ document_id: documentId, file_name: fileName, mime_type: 'text/plain', storage_provider: 'MedFlow secure document storage', storage_reference: `clinical-documents/${documentId}/original.txt`, file_url: `data:text/plain;charset=utf-8,${encodeURIComponent(content)}` })

const sourceDocuments: SourceDocument[] = [{
  document_id: 'doc_5521',
  file_name: 'Ananya_Mehta_clinical_record_2026-08-17.pdf',
  mime_type: 'application/pdf',
  storage_provider: 'MedFlow secure document storage',
  storage_reference: 'clinical-documents/doc_5521/original.pdf',
  file_url: 'data:application/pdf;base64,JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2JqCjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2JqCjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIgNzkyXSAvQ29udGVudHMgNCAwIFIgL1Jlc291cmNlcyA8PCAvRm9udCA8PCAvRjEgNSAwIFIgPj4gPj4gPj4KZW5kb2JqCjQgMCBvYmoKPDwgL0xlbmd0aCAxMTkgPj4Kc3RyZWFtCkJUCi9GMSAxOCBUZgo3MiA3MjAgVGQKKENsaW5pY2FsIHNvdXJjZSBkb2N1bWVudCkgVGoKMCAtMzIgVGQKKFBlbmljaWxsaW4gYWxsZXJneSByZXBvcnRlZCkgVGoKMCAtMzIgVGQKKE1ldGZvcm1pbiA1MDAgbWcgdHdpY2UgZGFpbHkpIFRqCkVUCmVuZHN0cmVhbQplbmRvYmoKNSAwIG9iago8PCAvVHlwZSAvRm9udCAvU3VidHlwZSAvVHlwZTEgL0Jhc2VGb250IC9IZWx2ZXRpY2EgPj4KZW5kb2JqCnhyZWYKMCA2CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDAwOSAwMDAwMCBuIAowMDAwMDAwMDU4IDAwMDAwIG4gCjAwMDAwMDAxMTUgMDAwMDAgbiAKMDAwMDAwMDI0MSAwMDAwMCBuIAowMDAwMDAwNDMyIDAwMDAwIG4gCnRyYWlsZXIKPDwgL1NpemUgNiAvUm9vdCAxIDAgUiA+PgpzdGFydHhyZWYKNTAyCiUlRU9GCg==',
},
  makeMockTextDocument('abha_seed_001', 'patient-history-abha-seed.txt', 'MedFlow patient history seed\nDocument ID: abha_seed_001\nNo known drug allergies\nHistory of hypertension'),
  makeMockTextDocument('doc_prior_001', 'prior-medication-record-001.txt', 'MedFlow prior medication record\nDocument ID: doc_prior_001\nMetformin 500 mg twice daily\nRoute: oral'),
  makeMockTextDocument('doc_prior_002', 'prior-medication-record-002.txt', 'MedFlow prior medication record\nDocument ID: doc_prior_002\nMetformin 1000 mg twice daily\nRoute: oral'),
  makeMockTextDocument('doc_prior_003', 'prior-medication-record-003.txt', 'MedFlow prior medication record\nDocument ID: doc_prior_003\nMetformin discontinued'),
]

export async function getSourceDocument(documentId: string): Promise<SourceDocument | null> {
  await pause()
  return sourceDocuments.find((document) => document.document_id === documentId) ?? null
}
