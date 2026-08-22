import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

/** Stops one broken component from taking the page with it.
 *
 * React unmounts the entire tree when an error escapes render, so a single
 * panel throwing — a diff view handed something that was not a diff, say —
 * left nothing but a white screen and no way back. A boundary turns that into
 * a message in the panel that broke, with the rest of the app still usable.
 */
export default class ErrorBoundary extends Component<
  { children: ReactNode; label?: string },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`${this.props.label ?? 'A panel'} crashed:`, error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div
        data-testid="error-boundary-fallback"
        className="h-full min-h-32 flex flex-col items-center justify-center gap-3 p-6 text-center"
      >
        <AlertTriangle size={24} className="text-warning" />
        <div className="text-sm text-text-secondary">
          {this.props.label ?? 'This panel'} hit an error and stopped.
        </div>
        <code className="max-w-full truncate text-xs text-text-muted font-mono">
          {error.message}
        </code>
        <button
          onClick={() => this.setState({ error: null })}
          className="px-3 py-1 text-sm rounded bg-control-bg hover:bg-control-bg-hover text-text-secondary"
        >
          Try again
        </button>
      </div>
    )
  }
}
