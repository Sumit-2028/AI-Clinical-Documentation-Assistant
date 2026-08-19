import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Conflict } from '../contracts/retrievedContext'

export type ConflictResolutionAction = 'keep_record_1' | 'keep_record_2' | 'mark_resolved' | 'reject_record_2'

export interface ConflictResolution {
  conflict_id: string
  action: ConflictResolutionAction
  resolved_at: string
}

interface ConflictResolutionContextValue {
  resolutions: Record<string, ConflictResolution>
  resolveConflict: (conflict: Conflict, action: ConflictResolutionAction) => void
  isResolved: (conflictId: string) => boolean
}

const ConflictResolutionContext = createContext<ConflictResolutionContextValue | null>(null)

export function ConflictResolutionProvider({ children }: { children: ReactNode }) {
  const [resolutions, setResolutions] = useState<Record<string, ConflictResolution>>({})
  const value = useMemo<ConflictResolutionContextValue>(() => ({
    resolutions,
    resolveConflict: (conflict, action) => setResolutions((current) => ({ ...current, [conflict.conflict_id]: { conflict_id: conflict.conflict_id, action, resolved_at: new Date().toISOString() } })),
    isResolved: (conflictId) => Boolean(resolutions[conflictId]),
  }), [resolutions])
  return <ConflictResolutionContext.Provider value={value}>{children}</ConflictResolutionContext.Provider>
}

export function useConflictResolutions() {
  const context = useContext(ConflictResolutionContext)
  if (!context) throw new Error('useConflictResolutions must be used inside ConflictResolutionProvider')
  return context
}
