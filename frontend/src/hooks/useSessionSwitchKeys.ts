import { useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { getApiBase } from '../config'
import { useIsDesktop } from './useMediaQuery'
import { parseSessionsPayload } from '../utils/sessionStatus'
import { orderSessionsForNavigator, adjacentSessionName } from '../utils/sessionOrder'

/** Alt+Left / Alt+Right step to the session beside this one in the switcher, from
 * anywhere on a session page — including while the terminal holds focus, which
 * Terminal.tsx arranges by letting the chord through to this window listener.
 *
 * Claiming the chord costs browser Back/Forward on the session pages; the in-app
 * back affordances stay available. */
export function useSessionSwitchKeys(currentSessionName: string | undefined) {
  const isDesktop = useIsDesktop()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (!isDesktop || !currentSessionName) return
    const routeSuffix = location.pathname.endsWith('/term') ? '/term' : ''

    const onKeyDown = async (e: KeyboardEvent) => {
      if (!e.altKey || e.ctrlKey || e.metaKey) return
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
      e.preventDefault()
      try {
        const res = await fetch(`${getApiBase()}/sessions`)
        if (!res.ok) return
        const ordered = orderSessionsForNavigator(parseSessionsPayload(await res.json()))
        const target = adjacentSessionName(
          ordered,
          currentSessionName,
          e.key === 'ArrowRight' ? 'next' : 'prev'
        )
        if (target) navigate(`/session/${target}${routeSuffix}`)
      } catch {
        // Ignore fetch errors
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [currentSessionName, isDesktop, location.pathname, navigate])
}
