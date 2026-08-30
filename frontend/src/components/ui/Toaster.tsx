import { useToast } from '../../hooks/toastContext'

/** Renders whatever toasts are live. Mounted once, near the app root.
 *
 * Bottom-centre rather than top-right: on a phone the top of the screen is the
 * session header and the notch, and a git action's failure needs to be readable
 * without covering the thing it is talking about. */
export default function Toaster() {
  const { toasts, dismiss } = useToast()
  if (!toasts.length) return null

  return (
    <div
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[60] flex flex-col gap-2 w-[min(32rem,calc(100vw-2rem))]"
      role="status"
      aria-live="polite"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          data-testid={`toast-${t.kind}`}
          className={`flex items-start gap-3 px-4 py-3 rounded-[var(--radius-lg)] border shadow-[var(--shadow-high)] text-sm ${
            t.kind === 'error'
              ? 'bg-bg-surface border-status-error text-text-primary'
              : 'bg-bg-surface border-border-default text-text-secondary'
          }`}
        >
          <div className="min-w-0 flex-1">
            <p className="break-words">{t.message}</p>
            {t.detail && (
              <p className="text-xs text-text-muted mt-1 break-all font-mono">{t.detail}</p>
            )}
          </div>
          <button
            type="button"
            onClick={() => dismiss(t.id)}
            aria-label="Dismiss"
            className="text-text-muted hover:text-text-primary shrink-0 leading-none"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
