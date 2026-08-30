import { createContext, useContext } from 'react'

export type ToastKind = 'error' | 'info'

export interface Toast {
  id: number
  kind: ToastKind
  message: string
  /** Optional second line: the detail that makes the message actionable. */
  detail?: string
}

export interface ToastApi {
  error: (message: string, detail?: string) => void
  info: (message: string, detail?: string) => void
  dismiss: (id: number) => void
  toasts: Toast[]
}

export const ToastContext = createContext<ToastApi | null>(null)

/** How long a toast stays up. Errors linger: they usually carry a path or a
 * branch name the reader needs long enough to act on. */
export const DISMISS_MS: Record<ToastKind, number> = { error: 9000, info: 4000 }

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used inside a ToastProvider')
  }
  return ctx
}
