import Modal from './ui/Modal'
import type { HarnessMissingDetail } from '../utils/billHarness'

interface Props {
  detail: HarnessMissingDetail | null
  onClose: () => void
  onUseFallback: (agent: string) => void
  switching?: boolean
}

export default function BillHarnessMissing({ detail, onClose, onUseFallback, switching }: Props) {
  if (!detail) return null
  const harness = detail.harness ?? 'the harness'
  const fallback = detail.fallback_agent

  return (
    <Modal open onClose={onClose} title={`Bill needs the ${harness} harness`}>
      <div className="space-y-4 text-sm">
        <p className="text-text-secondary">
          Bill is not installed as part of Lumbergh. He runs under{' '}
          <code className="px-1 rounded bg-bg-inset">{harness}</code>, a separate tool you install
          yourself, and it is not on this machine.
        </p>

        {detail.why && <p className="text-text-muted text-xs">{detail.why}</p>}

        <div className="flex flex-col gap-2">
          {detail.install_url && (
            <a
              href={detail.install_url}
              target="_blank"
              rel="noreferrer"
              className="text-accent-primary hover:underline"
              data-testid="bill-harness-install-link"
            >
              How to install {harness} →
            </a>
          )}

          {fallback ? (
            <button
              type="button"
              onClick={() => onUseFallback(fallback)}
              disabled={switching}
              data-testid="bill-harness-use-fallback"
              className="self-start px-3 py-1.5 rounded-[var(--radius-md)] border border-border-default hover:bg-bg-hover disabled:opacity-50"
            >
              {switching ? 'Switching…' : `Run Bill with ${fallback} instead`}
            </button>
          ) : (
            <p className="text-text-muted text-xs">
              Set a default agent in Settings to run Bill without {harness}.
            </p>
          )}
        </div>

        {fallback && (
          <p className="text-text-muted text-xs">
            Bill supervises in a loop, so {fallback} will cost more than {harness} would. You can
            change this any time under Settings → Bill.
          </p>
        )}
      </div>
    </Modal>
  )
}
