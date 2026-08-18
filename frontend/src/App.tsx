import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { UploadPage } from './pages/UploadPage'
import { ReviewQueuePage } from './pages/ReviewQueuePage'
import { VerificationPage } from './pages/VerificationPage'
import { AuditLogPage } from './pages/AuditLogPage'
import { ClinicalNlpPage } from './pages/ClinicalNlpPage'
import { MemoryExplorerPage } from './pages/MemoryExplorerPage'
import {
  DocumentationPage,
  DocumentReviewPage,
  DocumentsPage,
} from './pages/DocumentationPage'
import {
  PlaceholderPage,
  ProcessingPage,
} from './pages/PlaceholderPage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { SignupPage } from './pages/SignupPage'
import { PatientsPage } from './pages/PatientsPage'
import { WorkflowProvider } from './context/WorkflowContext'
import { AuthProvider, useAuth } from './context/AuthContext'

export function App() {
  return (
    <AuthProvider>
      <WorkflowProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />

          <Route element={<RequireAuth />}>
            <Route element={<Layout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/processing" element={<ProcessingPage />} />
              <Route path="/clinical-nlp" element={<ClinicalNlpPage />} />
              <Route path="/review-queue" element={<ReviewQueuePage />} />
              <Route path="/verification" element={<VerificationPage />} />
              <Route path="/audit-log" element={<AuditLogPage />} />
              <Route path="/patients" element={<PatientsPage />} />
              <Route path="/memory" element={<MemoryExplorerPage />} />
              <Route
                path="/conflicts"
                element={<MemoryExplorerPage initialView="conflicts" />}
              />
              <Route path="/documentation" element={<DocumentationPage />} />
              <Route
                path="/documentation/review"
                element={<DocumentReviewPage />}
              />
              <Route path="/documents" element={<DocumentsPage />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </WorkflowProvider>
    </AuthProvider>
  )
}

function RequireAuth() {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <div className="empty-loading">Restoring secure session…</div>
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname }}
      />
    )
  }

  return <Outlet />
}
