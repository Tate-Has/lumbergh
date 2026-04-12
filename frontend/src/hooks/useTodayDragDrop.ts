import { useState, useCallback, useRef } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TodayInsertGap {
  beforeTaskId: string | null
  /** CSS left offset relative to the grid container */
  left: number
  /** CSS top offset relative to the grid container */
  top: number
  /** Height of the adjacent card (used to size the indicator) */
  height: number
}

/** Internal extended gap used during distance calculation. */
interface InsertGapInternal extends TodayInsertGap {
  /** Absolute X coordinate used for Euclidean distance */
  gx: number
  /** Absolute Y coordinate used for Euclidean distance */
  gy: number
}

export interface UseTodayDragDrop {
  /** The nearest insert gap (or null when no gap is found). */
  indicatorGap: TodayInsertGap | null
  /** Whether the indicator should be visible (drag is over the container). */
  indicatorVisible: boolean
  /** Spread these onto the grid container element. */
  containerProps: {
    onDragOver: (e: React.DragEvent) => void
    onDragLeave: (e: React.DragEvent) => void
    onDrop: (e: React.DragEvent) => void
  }
}

// ---------------------------------------------------------------------------
// Pure helper -- exported so useTouchDrag can reuse it
// ---------------------------------------------------------------------------

/**
 * Given a today-grid container and a pointer position (clientX/clientY),
 * find the nearest insert gap by Euclidean distance.
 *
 * This is intentionally a plain function (not a hook) so it can be called
 * from both React event handlers and native touch handlers.
 */
export function findTodayInsertGap(
  gridContainer: HTMLElement,
  x: number,
  y: number
): TodayInsertGap | null {
  const cards = [...gridContainer.querySelectorAll('.today-card:not(.dragging)')] as HTMLElement[]

  if (!cards.length) return null

  const containerRect = gridContainer.getBoundingClientRect()

  const gaps: InsertGapInternal[] = []

  for (const card of cards) {
    const rect = card.getBoundingClientRect()
    gaps.push({
      beforeTaskId: card.dataset.taskId ?? null,
      gx: rect.left,
      gy: rect.top + rect.height / 2,
      left: rect.left - containerRect.left - 4,
      top: rect.top - containerRect.top,
      height: rect.height,
    })
  }

  // End gap after the last card
  const lastCard = cards[cards.length - 1]!
  const lastRect = lastCard.getBoundingClientRect()
  gaps.push({
    beforeTaskId: null,
    gx: lastRect.right,
    gy: lastRect.top + lastRect.height / 2,
    left: lastRect.right - containerRect.left + 1,
    top: lastRect.top - containerRect.top,
    height: lastRect.height,
  })

  // Find nearest gap by Euclidean distance
  let nearest: InsertGapInternal | null = null
  let nearestDist = Infinity
  for (const gap of gaps) {
    const dist = Math.hypot(x - gap.gx, y - gap.gy)
    if (dist < nearestDist) {
      nearestDist = dist
      nearest = gap
    }
  }

  if (!nearest) return null

  // Strip internal fields before returning
  return {
    beforeTaskId: nearest.beforeTaskId,
    left: nearest.left,
    top: nearest.top,
    height: nearest.height,
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * React hook for Today panel drag-and-drop reordering.
 *
 * Usage:
 * ```tsx
 * const { indicatorGap, indicatorVisible, containerProps } = useTodayDragDrop(
 *   gridRef,
 *   (taskId, beforeTaskId) => moveTask(taskId, 'today', beforeTaskId),
 * );
 *
 * <div ref={gridRef} className="today-grid" {...containerProps}>
 *   {cards}
 *   {indicatorVisible && indicatorGap && (
 *     <div
 *       className="today-insert-indicator visible"
 *       style={{ left: indicatorGap.left, top: indicatorGap.top, height: indicatorGap.height }}
 *     />
 *   )}
 * </div>
 * ```
 */
export function useTodayDragDrop(
  containerRef: React.RefObject<HTMLElement | null>,
  onDrop: (taskId: string, beforeTaskId: string | null) => void
): UseTodayDragDrop {
  const [indicatorGap, setIndicatorGap] = useState<TodayInsertGap | null>(null)
  const [indicatorVisible, setIndicatorVisible] = useState(false)

  // Keep a ref to the latest gap so the drop handler can read it synchronously
  // without waiting for a React re-render.
  const latestGapRef = useRef<TodayInsertGap | null>(null)

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'

      const container = containerRef.current
      if (!container) return

      const gap = findTodayInsertGap(container, e.clientX, e.clientY)
      latestGapRef.current = gap

      if (gap) {
        setIndicatorGap(gap)
        setIndicatorVisible(true)
      } else {
        setIndicatorVisible(false)
      }
    },
    [containerRef]
  )

  const handleDragLeave = useCallback(
    (e: React.DragEvent) => {
      const container = containerRef.current
      if (!container) return

      // Only hide when the pointer actually leaves the container
      // (not when entering a child element).
      if (!container.contains(e.relatedTarget as Node)) {
        setIndicatorVisible(false)
      }
    },
    [containerRef]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()

      // Remove drag-over highlight from parent panel (stopPropagation
      // prevents the panel's own onDrop from firing).
      const container = containerRef.current
      container?.closest('.panel')?.classList.remove('drag-over')

      const taskId = e.dataTransfer?.getData('text/plain')
      if (!taskId) return

      // Use the ref for the most up-to-date gap (avoids stale closure from
      // the last setState batch).
      const gap = latestGapRef.current
      const beforeTaskId = gap ? gap.beforeTaskId : null

      setIndicatorVisible(false)
      setIndicatorGap(null)
      latestGapRef.current = null

      onDrop(taskId, beforeTaskId)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- containerRef is a stable ref object; its .current is accessed inside the handler, not needed in dep array
    [onDrop]
  )

  return {
    indicatorGap,
    indicatorVisible,
    containerProps: {
      onDragOver: handleDragOver,
      onDragLeave: handleDragLeave,
      onDrop: handleDrop,
    },
  }
}
