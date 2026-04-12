import { useState, useEffect, useRef, useCallback } from 'react'
import { useLocalStorage } from './useLocalStorage'
import { getApiBase } from '../config'

interface UseNotes {
  notesContent: string
  setNotesContent: (content: string) => void
  saveNotes: () => void
  loadNotes: () => Promise<void>
  notesOpen: boolean
  setNotesOpen: (open: boolean) => void
}

export function useNotes(): UseNotes {
  const [notesContent, setNotesContentState] = useState('')
  const [notesOpen, setNotesOpen] = useLocalStorage('lumbergh:focus:notes_open', false)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const contentRef = useRef(notesContent)

  // Keep ref in sync so the save closure always has the latest content
  // eslint-disable-next-line react-hooks/refs -- intentional ref-sync pattern: updated during render so stable callback always sees latest value
  contentRef.current = notesContent

  const saveNotes = useCallback(() => {
    fetch(`${getApiBase()}/focus/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: contentRef.current }),
    }).catch(() => {
      /* ignore save errors */
    })
  }, [])

  const setNotesContent = useCallback(
    (content: string) => {
      setNotesContentState(content)
      contentRef.current = content

      // Debounced save (500ms)
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
      saveTimeoutRef.current = setTimeout(() => saveNotes(), 500)
    },
    [saveNotes]
  )

  const loadNotes = useCallback(async () => {
    try {
      const res = await fetch(`${getApiBase()}/focus/notes`)
      const json = await res.json()
      const content = json.content || ''
      setNotesContentState(content)
      contentRef.current = content
    } catch {
      /* ignore load errors */
    }
  }, [])

  // Load on mount
  useEffect(() => {
    loadNotes()
  }, [loadNotes])

  // Cleanup pending timeout on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    }
  }, [])

  return {
    notesContent,
    setNotesContent,
    saveNotes,
    loadNotes,
    notesOpen,
    setNotesOpen,
  }
}
