import { useEffect } from 'react'

interface ShortcutHandlers {
  onNewInbox?: () => void
  onFocusToday?: () => void
  onToggleTheme?: () => void
  onShowHelp?: () => void
  onEscape?: () => void
}

export function useKeyboardShortcuts(handlers: ShortcutHandlers): void {
  useEffect(() => {
    // eslint-disable-next-line complexity -- inherited keyboard shortcut handler; refactoring out of scope
    function handleKeyDown(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName
      const isEditable =
        tag === 'INPUT' ||
        tag === 'TEXTAREA' ||
        tag === 'SELECT' ||
        (e.target as HTMLElement).isContentEditable

      // Escape always fires, even in editable elements
      if (e.key === 'Escape') {
        handlers.onEscape?.()
        return
      }

      // Skip shortcuts when typing in form fields
      if (isEditable) return

      // Skip when modifier keys are held (except Escape handled above)
      if (e.ctrlKey || e.metaKey || e.altKey) return

      switch (e.key) {
        case 'n':
          e.preventDefault()
          handlers.onNewInbox?.()
          break
        case 't':
          handlers.onFocusToday?.()
          break
        case 'd':
          handlers.onToggleTheme?.()
          break
        case '?':
          handlers.onShowHelp?.()
          break
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [handlers])
}
