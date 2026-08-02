/** Confirm text for retiring Bill from the dashboard.
 *
 * Names any overseers he is currently babysitting, because those loops are server-owned
 * and keep cycling after Bill is gone — the user should know they'll run unmonitored
 * (no one advancing a stall) until Bill is summoned again. */
export function buildBillStopMessage(babysatSessions: string[]): string {
  const base =
    'Stop Bill?\n\n' +
    'His working context will be lost. His preferences.md is kept, and you can summon ' +
    'him again anytime.'
  if (babysatSessions.length === 0) return base

  const noun = babysatSessions.length === 1 ? 'session' : 'sessions'
  return (
    `${base}\n\n` +
    `Bill is babysitting ${babysatSessions.length} ${noun}: ${babysatSessions.join(', ')}. ` +
    'Those loops keep running unmonitored until you summon Bill again.'
  )
}
