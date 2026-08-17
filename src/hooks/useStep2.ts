import { useQuery } from '@tanstack/react-query'
import { getStep2Job, processStep2 } from '../api'

export function useClinicalNlpOutput() {
  return useQuery({ queryKey: ['step2-clinical-nlp'], queryFn: () => getStep2Job('job_nlp_412') })
}

export function useProcessClinicalNlp() {
  return useQuery({ queryKey: ['step2-process'], queryFn: processStep2, enabled: false })
}
