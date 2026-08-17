import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { ProcessingStatus } from '../contracts/common'

export type WorkflowStage =
  | 'upload'
  | 'extraction'
  | 'confidence'
  | 'verification'
  | 'clinical-intelligence'
  | 'abbreviation-review'
  | 'nlp-processing'
  | 'entity-extraction'
  | 'clinical-context'
  | 'finding-review'
  | 'safety-check'
  | 'patient-memory'

export type ReviewStatus = 'pending' | 'complete'
export type NlpStatus = 'pending' | 'processing' | 'complete' | 'failed'
export type SafetyStatus = 'blocked' | 'ready'

export interface WorkflowState {
  patient_id: string
  encounter_id: string
  document_id: string
  processing_status: ProcessingStatus
  current_stage: WorkflowStage
  abbreviation_review_status: ReviewStatus
  nlp_status: NlpStatus
  clinical_finding_review_status: ReviewStatus
  safety_status: SafetyStatus
}

const testWorkflow = import.meta.env.MODE === 'test'

export const defaultWorkflowState: WorkflowState = {
  patient_id: testWorkflow ? 'pat_00123' : '',
  encounter_id: testWorkflow ? 'enc_2026_0817_01' : '',
  document_id: testWorkflow ? 'doc_5521' : '',
  processing_status: 'pending_human_verification',
  current_stage: testWorkflow ? 'verification' : 'upload',
  abbreviation_review_status: 'pending',
  nlp_status: 'pending',
  clinical_finding_review_status: 'pending',
  safety_status: 'blocked',
}

export interface WorkflowNavigationState {
  workflow?: WorkflowState
}

interface WorkflowContextValue {
  workflow: WorkflowState
  setWorkflow: (update: Partial<WorkflowState>) => void
  beginProcessing: (values: Pick<WorkflowState, 'patient_id' | 'encounter_id' | 'document_id' | 'processing_status'>) => WorkflowState
}

const WorkflowContext = createContext<WorkflowContextValue | null>(null)
const standaloneWorkflowContext: WorkflowContextValue = {
  workflow: defaultWorkflowState,
  setWorkflow: () => undefined,
  beginProcessing: (values) => ({ ...defaultWorkflowState, ...values, current_stage: 'clinical-intelligence', safety_status: 'blocked' }),
}

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [workflow, setWorkflowState] = useState<WorkflowState>(defaultWorkflowState)
  const value = useMemo<WorkflowContextValue>(() => ({
    workflow,
    setWorkflow: (update) => setWorkflowState((current) => ({ ...current, ...update })),
    beginProcessing: (values) => {
      const next: WorkflowState = {
        ...workflow,
        ...values,
        current_stage: 'clinical-intelligence',
        abbreviation_review_status: 'pending',
        nlp_status: 'pending',
        clinical_finding_review_status: 'pending',
        safety_status: 'blocked',
      }
      setWorkflowState(next)
      return next
    },
  }), [workflow])

  return <WorkflowContext.Provider value={value}>{children}</WorkflowContext.Provider>
}

export function useWorkflow() {
  const context = useContext(WorkflowContext)
  return context ?? standaloneWorkflowContext
}

export const workflowStageOrder: WorkflowStage[] = [
  'upload',
  'extraction',
  'confidence',
  'verification',
  'clinical-intelligence',
  'abbreviation-review',
  'nlp-processing',
  'entity-extraction',
  'clinical-context',
  'finding-review',
  'safety-check',
  'patient-memory',
]
