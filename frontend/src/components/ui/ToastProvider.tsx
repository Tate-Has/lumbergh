import { useCallback, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import {
  DISMISS_MS,
  ToastContext,
  type Toast,
  type ToastApi,
  type ToastKind,
} from '../../hooks/toastContext'

export default function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const push = useCallback(
    (kind: ToastKind, message: string, detail?: string) => {
      const id = nextId.current++
      setToasts((prev) => [...prev.slice(-3), { id, kind, message, detail }])
      setTimeout(() => dismiss(id), DISMISS_MS[kind])
    },
    [dismiss]
  )

  const api = useMemo<ToastApi>(
    () => ({
      error: (message, detail) => push('error', message, detail),
      info: (message, detail) => push('info', message, detail),
      dismiss,
      toasts,
    }),
    [push, dismiss, toasts]
  )

  return <ToastContext.Provider value={api}>{children}</ToastContext.Provider>
}
