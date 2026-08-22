import { describe, it, expect } from 'vitest'
import { PROVIDERS } from './aiProviders'

describe('the AI provider registry', () => {
  it('leads with the one that needs no key', () => {
    expect(PROVIDERS[0].id).toBe('claude_cli')
  })

  it('asks the CLI provider for nothing but a model', () => {
    const claudeCli = PROVIDERS.find((p) => p.id === 'claude_cli')!

    expect(claudeCli.fields.map((f) => f.key)).toEqual(['model'])
    expect(claudeCli.defaultModel).toBe('haiku')
  })
})
