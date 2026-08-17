import type { RiskLevel } from './common'
import type { MemoryFact } from './memory'

export interface Conflict {
  conflict_id: string
  concept_thread: string
  risk_level: RiskLevel
  status: 'unresolved' | 'resolved' | 'dismissed'
  event_a: MemoryFact
  event_b: MemoryFact
}

export interface RetrievedContext {
  verified_context: {
    conditions: MemoryFact[]
    medications: MemoryFact[]
    allergies: MemoryFact[]
    procedures: MemoryFact[]
    lab_trends: MemoryFact[]
    significant_events: MemoryFact[]
  }
  unverified_information: MemoryFact[]
  conflicts: Conflict[]
}

export type RetrievedFact = MemoryFact
