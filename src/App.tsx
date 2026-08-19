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
import { PatientsPage } from './pages/PatientsPage'
import { ProcessingPage } from './pages/PlaceholderPage'
import { WorkflowProvider } from './context/WorkflowContext'
import { ConflictResolutionProvider } from './context/ConflictResolutionContext'
import { ResolveConflictPage } from './pages/ResolveConflictPage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { SignupPage } from './pages/SignupPage'
import { isDemoSessionActive } from './lib/demoSession'

function RootRoute() { return isDemoSessionActive() ? <Layout><DashboardPage /></Layout> : <LandingPage /> }

export function App() { return <WorkflowProvider><ConflictResolutionProvider><Routes><Route path="/" element={<RootRoute />} /><Route path="/login" element={<LoginPage />} /><Route path="/signup" element={<SignupPage />} /><Route element={<Layout />}><Route path="/upload" element={<UploadPage />} /><Route path="/processing" element={<ProcessingPage />} /><Route path="/clinical-nlp" element={<ClinicalNlpPage />} /><Route path="/review-queue" element={<ReviewQueuePage />} /><Route path="/verification" element={<VerificationPage />} /><Route path="/audit-log" element={<AuditLogPage />} /><Route path="/patients" element={<PatientsPage />} /><Route path="/memory" element={<MemoryExplorerPage />} /><Route path="/conflicts" element={<MemoryExplorerPage initialView="conflicts" />} /><Route path="/resolve-conflict" element={<ResolveConflictPage />} /><Route path="/documentation" element={<DocumentationPage />} /><Route path="/documentation/review" element={<DocumentReviewPage />} /><Route path="/documents" element={<DocumentsPage />} /></Route></Routes></ConflictResolutionProvider></WorkflowProvider> }
