interface Props {
  harness: string
  onHarnessChange: (value: string) => void
  agentProviders: Record<string, { label: string }>
  personality: string
  onPersonalityChange: (value: string) => void
  customPersonality: string
  onCustomPersonalityChange: (value: string) => void
}

const PRESETS: { id: string; label: string; description: string }[] = [
  {
    id: 'professional',
    label: 'Professional',
    description: 'Direct, brief, factual. Leads with outcomes and never pads a report.',
  },
  {
    id: 'lumbergh',
    label: 'Bill Lumbergh',
    description: 'The bit — "if you could go ahead and…". A light garnish over real reports.',
  },
  {
    id: 'custom',
    label: 'Custom',
    description: 'Write your own personality preamble.',
  },
]

export default function BillSettings({
  harness,
  onHarnessChange,
  agentProviders,
  personality,
  onPersonalityChange,
  customPersonality,
  onCustomPersonalityChange,
}: Props) {
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm text-text-tertiary mb-1">Harness</label>
        <select
          value={harness}
          onChange={(e) => onHarnessChange(e.target.value)}
          className="w-full px-3 py-2 bg-input-bg text-text-primary rounded-[var(--radius-lg)] border border-input-border focus:outline-none focus:border-action/50 text-sm"
        >
          {Object.entries(agentProviders).map(([key, provider]) => (
            <option key={key} value={key}>
              {provider.label}
            </option>
          ))}
        </select>
        <p className="text-xs text-text-muted mt-1">The coding agent Bill runs as.</p>
      </div>

      <div>
        <label className="block text-sm text-text-tertiary mb-2">Personality</label>
        <div className="space-y-2">
          {PRESETS.map((preset) => (
            <label key={preset.id} className="flex items-start gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                name="bill-personality"
                value={preset.id}
                checked={personality === preset.id}
                onChange={() => onPersonalityChange(preset.id)}
                className="mt-1"
              />
              <span>
                <span className="text-text-secondary">{preset.label}</span>
                <span className="block text-xs text-text-muted">{preset.description}</span>
              </span>
            </label>
          ))}
        </div>
        {personality === 'custom' && (
          <textarea
            value={customPersonality}
            onChange={(e) => onCustomPersonalityChange(e.target.value)}
            rows={5}
            maxLength={4000}
            placeholder={
              "You are Bill, the user's engineering manager. …\n\n" +
              'This voice is for you and no one else — it never reaches a worker or a tool.'
            }
            className="w-full mt-2 px-3 py-2 bg-input-bg text-text-primary rounded-[var(--radius-lg)] border border-input-border focus:outline-none focus:border-action/50 text-sm font-mono"
          />
        )}
      </div>

      <p className="text-xs text-text-muted">Changes apply the next time Bill is summoned.</p>
    </div>
  )
}
