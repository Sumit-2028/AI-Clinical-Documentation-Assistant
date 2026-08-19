import { CheckIcon } from './icons'
import { useWorkflow, workflowStageOrder, type WorkflowStage } from '../context/WorkflowContext'

const clinicalStages: Array<{ label: string; stage: WorkflowStage }> = [
  { label: 'Abbreviation review', stage: 'abbreviation-review' },
  { label: 'Entity extraction', stage: 'entity-extraction' },
  { label: 'Clinical context', stage: 'clinical-context' },
  { label: 'Clinical findings', stage: 'finding-review' },
  { label: 'Safety check', stage: 'safety-check' },
]

function stepState(currentStage: WorkflowStage, stage: WorkflowStage) {
  const visibleStage = currentStage === 'nlp-processing' ? 'entity-extraction' : currentStage
  const currentIndex = workflowStageOrder.indexOf(visibleStage)
  const stepIndex = workflowStageOrder.indexOf(stage)
  return stepIndex < currentIndex ? 'done' : stepIndex === currentIndex ? 'current' : ''
}

export function WorkflowProgress({ detail = false }: { detail?: boolean }) {
  const { workflow } = useWorkflow()
  return <>
    {detail && <div className="nlp-timeline clinical-review-progress" aria-label="Clinical intelligence workflow">
      {clinicalStages.map(({ label, stage }, index) => <div className={`nlp-stage ${stepState(workflow.current_stage, stage)}`} key={stage}>
        <div className="nlp-stage-marker">{stepState(workflow.current_stage, stage) === 'done' ? <CheckIcon /> : <span>{index + 1}</span>}</div>
        <span>{label}</span>
        {index < clinicalStages.length - 1 && <div className="nlp-stage-line" />}
      </div>)}
    </div>}
  </>
}
