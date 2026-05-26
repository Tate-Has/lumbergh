import { useState, useCallback, useRef } from 'react'

interface DragHandlers {
  draggable: boolean
  onDragStart: (e: React.DragEvent) => void
  onDragEnd: (e: React.DragEvent) => void
}

interface DropZoneHandlers {
  onDragOver: (e: React.DragEvent) => void
  onDragLeave: (e: React.DragEvent) => void
  onDrop: (e: React.DragEvent) => void
}

interface UseDragDrop {
  draggedTaskId: string | null
  getDragHandlers: (taskId: string) => DragHandlers
  getDropZoneHandlers: (onDrop: (taskId: string) => void) => DropZoneHandlers
  getInsertLineProps: (
    containerRef: React.RefObject<HTMLElement | null>,
    status: string,
    onDrop: (taskId: string, status: string, beforeTaskId: string | null) => void
  ) => {
    onDragOver: (e: React.DragEvent) => void
    onDragLeave: (e: React.DragEvent) => void
    onDrop: (e: React.DragEvent) => void
    activeBeforeTaskId: string | null
  }
}

/**
 * Extracts the task ID from a drag event, falling back to state if dataTransfer
 * is empty (e.g. on Firefox/touch polyfill).
 */
function extractTaskId(e: React.DragEvent, fallback: string | null): string | null {
  return e.dataTransfer.getData('text/plain') || fallback
}

/**
 * Given a container element and a cursor Y position, finds the beforeTaskId for
 * the closest insert gap among the kanban cards in the container.
 *
 * Returns the task ID of the card the dragged item should be inserted before,
 * or null if it should be appended at the end.
 */
function findClosestInsertPosition(container: HTMLElement, clientY: number): string | null {
  const cards = container.querySelectorAll<HTMLElement>('.kanban-card')
  if (cards.length === 0) return null

  interface Gap {
    beforeTaskId: string | null
    y: number
  }

  const gaps: Gap[] = []

  // One gap before each card (at the card's top edge midpoint)
  for (const card of cards) {
    const rect = card.getBoundingClientRect()
    gaps.push({
      beforeTaskId: card.dataset.taskId || null,
      y: rect.top + rect.height / 2,
    })
  }

  // One gap at the end (below the last card)
  const lastCard = cards[cards.length - 1]!
  const lastRect = lastCard.getBoundingClientRect()
  gaps.push({
    beforeTaskId: null, // null = append at end
    y: lastRect.bottom,
  })

  let closest: Gap = gaps[0]!
  let closestDist = Math.abs(clientY - closest.y)
  for (let i = 1; i < gaps.length; i++) {
    const dist = Math.abs(clientY - gaps[i]!.y)
    if (dist < closestDist) {
      closestDist = dist
      closest = gaps[i]!
    }
  }

  return closest.beforeTaskId
}

export function useDragDrop(): UseDragDrop {
  const [draggedTaskId, setDraggedTaskId] = useState<string | null>(null)
  const [activeBeforeTaskId, setActiveBeforeTaskId] = useState<string | null>(null)

  // Ref to keep the current draggedTaskId accessible in callbacks that close
  // over stale state (e.g. onDrop firing before the next render).
  const draggedRef = useRef<string | null>(null)

  // ---- Drag source handlers (for draggable cards) --------------------------

  const getDragHandlers = useCallback(
    (taskId: string): DragHandlers => ({
      draggable: true,

      onDragStart: (e: React.DragEvent) => {
        draggedRef.current = taskId
        setDraggedTaskId(taskId)
        e.dataTransfer.effectAllowed = 'move'
        e.dataTransfer.setData('text/plain', taskId)
        // Add class after a tick so the browser captures the un-faded element
        // as the drag image.
        const el = e.currentTarget as HTMLElement
        setTimeout(() => el.classList.add('dragging'), 0)
      },

      onDragEnd: (e: React.DragEvent) => {
        ;(e.currentTarget as HTMLElement).classList.remove('dragging')
        draggedRef.current = null
        setDraggedTaskId(null)
      },
    }),
    []
  )

  // ---- Simple drop zone handlers (Today panel, InFlight panel) -------------

  const getDropZoneHandlers = useCallback(
    (onDrop: (taskId: string) => void): DropZoneHandlers => ({
      onDragOver: (e: React.DragEvent) => {
        e.preventDefault()
        e.dataTransfer.dropEffect = 'move'
        ;(e.currentTarget as HTMLElement).classList.add('drag-over')
      },

      onDragLeave: (e: React.DragEvent) => {
        const container = e.currentTarget as HTMLElement
        if (!container.contains(e.relatedTarget as Node)) {
          container.classList.remove('drag-over')
        }
      },

      onDrop: (e: React.DragEvent) => {
        e.preventDefault()
        ;(e.currentTarget as HTMLElement).classList.remove('drag-over')
        const taskId = extractTaskId(e, draggedRef.current)
        if (taskId) onDrop(taskId)
      },
    }),
    []
  )

  // ---- Insert-line column handlers (Board kanban columns) ------------------

  const getInsertLineProps = useCallback(
    (
      containerRef: React.RefObject<HTMLElement | null>,
      status: string,
      onDrop: (taskId: string, status: string, beforeTaskId: string | null) => void
    ) => ({
      onDragOver: (e: React.DragEvent) => {
        e.preventDefault()
        e.dataTransfer.dropEffect = 'move'
        const container = containerRef.current
        if (!container) return
        const before = findClosestInsertPosition(container, e.clientY)
        setActiveBeforeTaskId(before)
      },

      onDragLeave: (e: React.DragEvent) => {
        const container = containerRef.current
        if (!container) return
        if (!container.contains(e.relatedTarget as Node)) {
          setActiveBeforeTaskId(null)
        }
      },

      onDrop: (e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        const taskId = extractTaskId(e, draggedRef.current)
        if (!taskId) return

        // Compute the drop position from current cursor, don't rely on stale
        // state from the last dragOver since React may batch updates.
        const container = containerRef.current
        let before: string | null = null
        if (container) {
          before = findClosestInsertPosition(container, e.clientY)
        }

        setActiveBeforeTaskId(null)
        onDrop(taskId, status, before)
      },

      activeBeforeTaskId,
    }),
    [activeBeforeTaskId]
  )

  return {
    draggedTaskId,
    getDragHandlers,
    getDropZoneHandlers,
    getInsertLineProps,
  }
}
