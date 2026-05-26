import { useEffect, useRef } from 'react'
import { findTodayInsertGap } from './useTodayDragDrop'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseTouchDragOptions {
  /** Called when a task card is dropped onto a valid drop zone. */
  onMoveTask: (taskId: string, newStatus: string, beforeTaskId: string | null) => void
  /** Called when a swimlane row is reordered via its drag handle. */
  onReorderSwimlane: (sourceProject: string, targetProject: string) => void
}

/** Internal mutable state stored in a ref (never triggers re-renders). */
interface TouchDragState {
  active: boolean
  ghost: HTMLElement | null
  sourceEl: HTMLElement | null
  taskId: string | null
  longPressTimer: ReturnType<typeof setTimeout> | null
  currentDropZone: HTMLElement | null
  isSwimlaneRow: boolean
  startX: number
  startY: number
  offsetX: number
  offsetY: number
}

const SCROLL_THRESHOLD = 10
const LONG_PRESS_MS = 300

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createGhost(el: HTMLElement, touch: Touch, dragState: TouchDragState): void {
  const rect = el.getBoundingClientRect()
  const ghost = el.cloneNode(true) as HTMLElement
  ghost.className = el.className + ' touch-ghost'
  ghost.style.cssText = `
    position: fixed;
    left: ${rect.left}px;
    top: ${rect.top}px;
    width: ${rect.width}px;
    opacity: 0.85;
    transform: scale(1.03);
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    pointer-events: none;
    z-index: 999;
    transition: none;
  `
  document.body.appendChild(ghost)
  dragState.ghost = ghost
  dragState.offsetX = touch.clientX - rect.left
  dragState.offsetY = touch.clientY - rect.top
}

function cleanupDrag(dragState: TouchDragState): void {
  if (dragState.ghost) {
    dragState.ghost.remove()
    dragState.ghost = null
  }
  if (dragState.sourceEl) {
    dragState.sourceEl.classList.remove('dragging')
    dragState.sourceEl = null
  }
  if (dragState.currentDropZone) {
    dragState.currentDropZone.classList.remove('drag-over')
    dragState.currentDropZone = null
  }
  document.querySelectorAll('.insert-line.visible').forEach((l) => l.classList.remove('visible'))
  document
    .querySelectorAll('.today-insert-indicator.visible')
    .forEach((i) => i.classList.remove('visible'))

  dragState.active = false
  dragState.taskId = null
  dragState.isSwimlaneRow = false
}

/**
 * Determine the target status from a drop zone element.
 * Returns null if the element is not a recognised drop zone.
 */
function resolveDropStatus(dropZone: HTMLElement): string | null {
  if (dropZone.dataset.status) {
    return dropZone.dataset.status
  }
  if (
    dropZone.id === 'todayGrid' ||
    dropZone.id === 'todayPanel' ||
    dropZone.closest('#todayPanel')
  ) {
    return 'today'
  }
  if (dropZone.id === 'sessionsPanel' || dropZone.closest('#sessionsPanel')) {
    return 'running'
  }
  if (dropZone.classList.contains('collapsed-col') && dropZone.dataset.status) {
    return dropZone.dataset.status
  }
  return null
}

/**
 * Find the nearest insert-line's `beforeTask` value for column-style
 * drop zones (kanban columns, swimlane cells).
 */
function findColumnBeforeId(dropZone: HTMLElement, clientY: number): string | null | undefined {
  const lines = dropZone.querySelectorAll('.insert-line')
  if (!lines.length) return undefined

  let closest: Element | null = null
  let closestDist = Infinity
  for (const line of lines) {
    const rect = line.getBoundingClientRect()
    const mid = rect.top + rect.height / 2
    const dist = Math.abs(clientY - mid)
    if (dist < closestDist) {
      closestDist = dist
      closest = line
    }
  }

  if (!closest) return undefined

  const bid = (closest as HTMLElement).dataset.beforeTask
  return bid === '__end__' ? null : (bid ?? null)
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Registers native touch event listeners on `document.body` to support
 * long-press drag-and-drop on mobile.
 *
 * Because this operates entirely outside React's synthetic event system
 * (ghost elements are appended to `document.body`, hit-testing uses
 * `document.elementFromPoint`), the hook manages all mutable state via
 * refs and never triggers re-renders.
 *
 * Cleanup removes all listeners and any lingering ghost elements.
 */
export function useTouchDrag(options: UseTouchDragOptions): void {
  // Capture callbacks via refs to avoid stale closures when the consumer
  // re-renders with new callback references.
  const onMoveTaskRef = useRef(options.onMoveTask)
  useEffect(() => {
    onMoveTaskRef.current = options.onMoveTask
  })

  const onReorderSwimlaneRef = useRef(options.onReorderSwimlane)
  useEffect(() => {
    onReorderSwimlaneRef.current = options.onReorderSwimlane
  })

  useEffect(() => {
    // -----------------------------------------------------------------------
    // Mutable drag state (never exposed to React render cycle)
    // -----------------------------------------------------------------------
    const dragState: TouchDragState = {
      active: false,
      ghost: null,
      sourceEl: null,
      taskId: null,
      longPressTimer: null,
      currentDropZone: null,
      isSwimlaneRow: false,
      startX: 0,
      startY: 0,
      offsetX: 0,
      offsetY: 0,
    }

    // -----------------------------------------------------------------------
    // touchstart
    // -----------------------------------------------------------------------
    function onTouchStart(e: TouchEvent): void {
      const draggable = (e.target as HTMLElement).closest(
        '[draggable="true"]'
      ) as HTMLElement | null
      if (!draggable) return

      const touch = e.touches[0]!
      dragState.startX = touch.clientX
      dragState.startY = touch.clientY

      const isHandle = draggable.classList.contains('drag-handle')
      const card = isHandle ? null : draggable
      const taskId = card ? (card.dataset.taskId ?? null) : null

      dragState.longPressTimer = setTimeout(() => {
        dragState.active = true
        dragState.isSwimlaneRow = isHandle

        if (isHandle) {
          dragState.sourceEl = draggable.closest('.swimlane-row') as HTMLElement | null
          dragState.taskId = null
          if (dragState.sourceEl) {
            dragState.sourceEl.classList.add('dragging')
            createGhost(dragState.sourceEl, touch, dragState)
          }
        } else {
          dragState.sourceEl = card
          dragState.taskId = taskId
          if (card) {
            card.classList.add('dragging')
            createGhost(card, touch, dragState)
          }
        }

        if (navigator.vibrate) navigator.vibrate(15)
      }, LONG_PRESS_MS)
    }

    // -----------------------------------------------------------------------
    // touchmove
    // -----------------------------------------------------------------------
    // eslint-disable-next-line complexity -- inherited touch DnD logic; refactoring out of scope
    function onTouchMove(e: TouchEvent): void {
      // Cancel long-press if finger moved too far (user is scrolling)
      if (dragState.longPressTimer && !dragState.active) {
        const touch = e.touches[0]!
        const dx = Math.abs(touch.clientX - dragState.startX)
        const dy = Math.abs(touch.clientY - dragState.startY)
        if (dx > SCROLL_THRESHOLD || dy > SCROLL_THRESHOLD) {
          clearTimeout(dragState.longPressTimer)
          dragState.longPressTimer = null
          return
        }
      }

      if (!dragState.active) return
      e.preventDefault()

      const touch = e.touches[0]!

      // Move the ghost element
      if (dragState.ghost) {
        dragState.ghost.style.left = touch.clientX - dragState.offsetX + 'px'
        dragState.ghost.style.top = touch.clientY - dragState.offsetY + 'px'
      }

      // Hit-test: hide ghost, probe element, restore ghost
      if (dragState.ghost) dragState.ghost.style.display = 'none'
      const hitEl = document.elementFromPoint(touch.clientX, touch.clientY) as HTMLElement | null
      if (dragState.ghost) dragState.ghost.style.display = ''

      if (!hitEl) return

      // ----- Swimlane row reorder -----
      if (dragState.isSwimlaneRow) {
        const targetRow = hitEl.closest('.swimlane-row') as HTMLElement | null
        if (targetRow !== dragState.currentDropZone) {
          if (dragState.currentDropZone) dragState.currentDropZone.classList.remove('drag-over')
          dragState.currentDropZone = targetRow
          if (targetRow && targetRow !== dragState.sourceEl) targetRow.classList.add('drag-over')
        }
        return
      }

      // ----- Task card drag -----
      const dropZone = hitEl.closest(
        '.col-cards, .swimlane-cell, .today-grid, .panel, .board-col.collapsed-col'
      ) as HTMLElement | null

      if (dropZone !== dragState.currentDropZone) {
        if (dragState.currentDropZone) dragState.currentDropZone.classList.remove('drag-over')
        dragState.currentDropZone = dropZone
        if (dropZone) dropZone.classList.add('drag-over')
      }

      if (!dropZone) return

      // Visual insert indicators
      if (dropZone.classList.contains('today-grid')) {
        const indicator = dropZone.querySelector('.today-insert-indicator') as HTMLElement | null
        if (indicator) {
          const gap = findTodayInsertGap(dropZone, touch.clientX, touch.clientY)
          if (gap) {
            indicator.style.left = gap.left + 'px'
            indicator.style.top = gap.top + 'px'
            indicator.style.height = gap.height + 'px'
            indicator.dataset.beforeTask = gap.beforeTaskId ?? '__end__'
            indicator.classList.add('visible')
          } else {
            indicator.classList.remove('visible')
          }
        }
      } else {
        // Column-style insert lines
        const lines = dropZone.querySelectorAll('.insert-line')
        if (lines.length) {
          let closest: Element | null = null
          let closestDist = Infinity
          for (const line of lines) {
            const rect = line.getBoundingClientRect()
            const mid = rect.top + rect.height / 2
            const dist = Math.abs(touch.clientY - mid)
            if (dist < closestDist) {
              closestDist = dist
              closest = line
            }
          }
          for (const line of lines) line.classList.toggle('visible', line === closest)
        }
      }
    }

    // -----------------------------------------------------------------------
    // touchend
    // -----------------------------------------------------------------------
    // eslint-disable-next-line complexity -- inherited touch DnD logic; refactoring out of scope
    function onTouchEnd(e: TouchEvent): void {
      if (dragState.longPressTimer) {
        clearTimeout(dragState.longPressTimer)
        dragState.longPressTimer = null
      }

      if (!dragState.active) return

      const touch = e.changedTouches[0]!

      // Hit-test under the finger
      if (dragState.ghost) dragState.ghost.style.display = 'none'
      const hitEl = document.elementFromPoint(touch.clientX, touch.clientY) as HTMLElement | null
      if (dragState.ghost) dragState.ghost.style.display = ''

      // ----- Swimlane row reorder -----
      if (dragState.isSwimlaneRow && dragState.sourceEl) {
        const targetRow = hitEl?.closest('.swimlane-row') as HTMLElement | null
        if (targetRow && targetRow !== dragState.sourceEl) {
          const sourceProject = dragState.sourceEl.dataset.project
          const targetProject = targetRow.dataset.project
          if (sourceProject && targetProject) {
            onReorderSwimlaneRef.current(sourceProject, targetProject)
          }
        }
        cleanupDrag(dragState)
        return
      }

      // ----- Task card drop -----
      if (dragState.taskId && hitEl) {
        const dropZone = hitEl.closest(
          '.col-cards, .swimlane-cell, .today-grid, .panel, .board-col.collapsed-col'
        ) as HTMLElement | null

        if (dropZone) {
          const newStatus = resolveDropStatus(dropZone)

          if (newStatus) {
            let beforeId: string | null = null

            if (dropZone.classList.contains('today-grid')) {
              // Use the shared gap finder for the Today grid
              const gap = findTodayInsertGap(dropZone, touch.clientX, touch.clientY)
              beforeId = gap ? gap.beforeTaskId : null
            } else {
              // Column insert-line approach
              const bid = findColumnBeforeId(dropZone, touch.clientY)
              if (bid !== undefined) {
                beforeId = bid
              }
            }

            onMoveTaskRef.current(dragState.taskId, newStatus, beforeId)
          }
        }
      }

      cleanupDrag(dragState)
    }

    // -----------------------------------------------------------------------
    // touchcancel
    // -----------------------------------------------------------------------
    function onTouchCancel(): void {
      if (dragState.longPressTimer) {
        clearTimeout(dragState.longPressTimer)
        dragState.longPressTimer = null
      }
      if (dragState.active) cleanupDrag(dragState)
    }

    // -----------------------------------------------------------------------
    // Register listeners
    // -----------------------------------------------------------------------
    document.body.addEventListener('touchstart', onTouchStart, {
      passive: false,
    })
    document.body.addEventListener('touchmove', onTouchMove, {
      passive: false,
    })
    document.body.addEventListener('touchend', onTouchEnd, {
      passive: false,
    })
    document.body.addEventListener('touchcancel', onTouchCancel, {
      passive: false,
    })

    // -----------------------------------------------------------------------
    // Cleanup
    // -----------------------------------------------------------------------
    return () => {
      document.body.removeEventListener('touchstart', onTouchStart)
      document.body.removeEventListener('touchmove', onTouchMove)
      document.body.removeEventListener('touchend', onTouchEnd)
      document.body.removeEventListener('touchcancel', onTouchCancel)

      // If a drag was in progress when the component unmounted, clean it up
      if (dragState.longPressTimer) {
        clearTimeout(dragState.longPressTimer)
        dragState.longPressTimer = null
      }
      cleanupDrag(dragState)
    }
  }, []) // Empty deps -- listeners are stable; callbacks accessed via refs
}
