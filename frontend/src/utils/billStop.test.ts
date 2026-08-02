import { describe, it, expect } from 'vitest'
import { buildBillStopMessage } from './billStop'

describe('buildBillStopMessage', () => {
  it('warns context is lost but preferences survive, and Bill can be re-summoned', () => {
    const msg = buildBillStopMessage([])
    expect(msg).toContain('context')
    expect(msg).toContain('preferences.md')
    expect(msg).toContain('summon')
  })

  it('names babysat sessions that will run unmonitored until re-summon', () => {
    const msg = buildBillStopMessage(['port', 'aio'])
    expect(msg).toContain('babysitting 2 sessions: port, aio')
    expect(msg).toContain('unmonitored')
  })

  it('uses the singular for a single babysat session', () => {
    expect(buildBillStopMessage(['port'])).toContain('babysitting 1 session: port')
  })
})
