import { useState, useEffect, useRef, useCallback } from 'react'
import type { PomodoroState, Task } from '../types/focus'

declare global {
  interface Window {
    pomo?: PomodoroState
  }
}

const POMO_WORK = 25 * 60
const POMO_BREAK = 5 * 60

export interface UsePomodoro {
  pomo: PomodoroState
  pomoStart: (taskId: string, tasks: Task[]) => void
  pomoPause: () => void
  pomoResume: () => void
  pomoStop: () => void
}

function pomoNotify(title: string, body: string): void {
  if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
    new Notification(title, { body })
  }
}

function pomoChime(): void {
  try {
    const ctx = new AudioContext()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.frequency.value = 880
    gain.gain.value = 0.1
    osc.start()
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5)
    osc.stop(ctx.currentTime + 0.5)
  } catch {
    /* audio not available */
  }
}

export function usePomodoro(): UsePomodoro {
  const pomoRef = useRef<PomodoroState>({
    active: false,
    running: false,
    taskId: null,
    taskTitle: '',
    phase: 'work',
    remaining: POMO_WORK,
    intervalId: null,
  })

  // eslint-disable-next-line react-hooks/refs -- reading ref in useState initializer is intentional; only runs once at mount
  const [pomo, setPomo] = useState<PomodoroState>({ ...pomoRef.current })

  // Expose pomoRef.current on window.pomo for Playwright tests (always, not just DEV)
  useEffect(() => {
    window.pomo = pomoRef.current
  }, [])

  const updatePomo = useCallback((updates: Partial<PomodoroState>) => {
    Object.assign(pomoRef.current, updates)
    setPomo({ ...pomoRef.current })
  }, [])

  // Tick function stored in a ref so the interval always sees the latest state
  const tickRef = useRef<() => void>(() => {})
  // eslint-disable-next-line react-hooks/refs -- intentional ref-sync pattern: tickRef updated each render so interval always sees latest state
  tickRef.current = () => {
    const ref = pomoRef.current
    ref.remaining--

    if (ref.remaining <= 0) {
      if (ref.phase === 'work') {
        ref.phase = 'break'
        ref.remaining = POMO_BREAK
        pomoNotify('Time for a break!', 'You focused for 25 minutes. Take 5.')
        pomoChime()
      } else {
        ref.phase = 'work'
        ref.remaining = POMO_WORK
        pomoNotify("Break's over!", 'Ready for another 25-minute focus session.')
        pomoChime()
      }
    }

    setPomo({ ...ref })
  }

  // Clean up interval on unmount
  useEffect(() => {
    const ref = pomoRef
    return () => {
      if (ref.current.intervalId) {
        clearInterval(ref.current.intervalId)
      }
    }
  }, [])

  const pomoStart = useCallback(
    (taskId: string, tasks: Task[]) => {
      // Clear existing interval if active
      if (pomoRef.current.active && pomoRef.current.intervalId) {
        clearInterval(pomoRef.current.intervalId)
      }

      // Request Notification permission
      if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
        Notification.requestPermission()
      }

      const task = tasks.find((t) => t.id === taskId)
      const intervalId = setInterval(() => tickRef.current(), 1000)

      updatePomo({
        active: true,
        running: true,
        taskId,
        taskTitle: task ? task.title : '',
        phase: 'work',
        remaining: POMO_WORK,
        intervalId,
      })
    },
    [updatePomo]
  )

  const pomoPause = useCallback(() => {
    const ref = pomoRef.current
    if (!ref.active || !ref.running) return

    if (ref.intervalId) clearInterval(ref.intervalId)
    updatePomo({ running: false, intervalId: null })
  }, [updatePomo])

  const pomoResume = useCallback(() => {
    const ref = pomoRef.current
    if (!ref.active || ref.running) return

    const intervalId = setInterval(() => tickRef.current(), 1000)
    updatePomo({ running: true, intervalId })
  }, [updatePomo])

  const pomoStop = useCallback(() => {
    if (pomoRef.current.intervalId) {
      clearInterval(pomoRef.current.intervalId)
    }

    updatePomo({
      active: false,
      running: false,
      taskId: null,
      taskTitle: '',
      phase: 'work',
      remaining: POMO_WORK,
      intervalId: null,
    })
  }, [updatePomo])

  return { pomo, pomoStart, pomoPause, pomoResume, pomoStop }
}
