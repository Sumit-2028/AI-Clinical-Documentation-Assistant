import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { UploadPage } from './pages/UploadPage'
import { ReviewQueuePage } from './pages/ReviewQueuePage'
import { VerificationPage } from './pages/VerificationPage'
import { AuditLogPage } from './pages/AuditLogPage'
import { ClinicalNlpPage } from './pages/ClinicalNlpPage'
import { MemoryExplorerPage } from './pages/MemoryExplorerPage'
import { DocumentationPage, DocumentReviewPage, DocumentsPage } from './pages/DocumentationPage'
import { PlaceholderPage, ProcessingPage } from './pages/PlaceholderPage'
import { WorkflowProvider } from './context/WorkflowContext'

export function App() { return <WorkflowProvider><Routes><Route element={<Layout />}><Route path="/" element={<DashboardPage />} /><Route path="/upload" element={<UploadPage />} /><Route path="/processing" element={<ProcessingPage />} /><Route path="/clinical-nlp" element={<ClinicalNlpPage />} /><Route path="/review-queue" element={<ReviewQueuePage />} /><Route path="/verification" element={<VerificationPage />} /><Route path="/audit-log" element={<AuditLogPage />} /><Route path="/patients" element={<PlaceholderPage title="Patients" section="patients" />} /><Route path="/memory" element={<MemoryExplorerPage />} /><Route path="/conflicts" element={<MemoryExplorerPage initialView="conflicts" />} /><Route path="/documentation" element={<DocumentationPage />} /><Route path="/documentation/review" element={<DocumentReviewPage />} /><Route path="/documents" element={<DocumentsPage />} /></Route></Routes></WorkflowProvider> }
