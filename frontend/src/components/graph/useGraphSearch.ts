import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { RefObject } from 'react'
import type { GraphData, GraphNode } from '../diff/types'
import { parseQuery, findMatches, isEmptyQuery, hashKey, anyRowVisible } from './graphSearch'

/** How far a non-matching commit fades. Still visible, clearly not a hit. */
const DIMMED = 0.12

/** Search and match-navigation state for the commit graph.
 *
 * Kept out of GitGraph so the component only asks two questions of it: is this
 * commit dimmed, and where is the next match.
 */
export function useGraphSearch({
  graphData,
  nodes,
  rowToY,
  rowHeight,
  containerRef,
  onSelectCommit,
}: {
  graphData: GraphData | null
  nodes: GraphNode[]
  rowToY: (row: number) => number
  rowHeight: number
  containerRef: RefObject<HTMLDivElement | null>
  onSelectCommit?: (hash: string) => void
}) {
  const [search, setSearch] = useState('')
  const [showHistorySearch, setShowHistorySearch] = useState(false)
  const matchCursor = useRef(-1)

  const commits = useMemo(() => graphData?.commits ?? [], [graphData])
  const query = useMemo(() => parseQuery(search), [search])
  const searching = !isEmptyQuery(query)
  const matches = useMemo(() => findMatches(commits, query), [commits, query])
  const loadedHashes = useMemo(() => new Set(commits.map((c) => hashKey(c.hash))), [commits])

  /** Row indices of matching commits, in the order they appear in the graph. */
  const matchRows = useMemo(
    () => nodes.map((n, row) => (matches.has(n.commit.hash) ? row : -1)).filter((r) => r >= 0),
    [nodes, matches]
  )

  useEffect(() => {
    matchCursor.current = -1
  }, [search])

  /** Non-matching commits fade rather than disappear: removing them would orphan
   *  their children and break the lane topology the layout assigns. */
  const dimOpacity = useCallback(
    (hash: string) => (searching && !matches.has(hash) ? DIMMED : 1),
    [searching, matches]
  )

  /** Walk to the next/previous match, wrapping, scrolling it into view and
   *  selecting it so the diff pane follows along. */
  const centreOnRow = useCallback(
    (row: number) => {
      const container = containerRef.current
      if (!container) return
      container.scrollTop = Math.max(0, rowToY(row) - container.clientHeight / 2 + rowHeight / 2)
    },
    [containerRef, rowToY, rowHeight]
  )

  const stepMatch = useCallback(
    (delta: number) => {
      if (matchRows.length === 0 || !containerRef.current) return
      const next =
        (((matchCursor.current + delta) % matchRows.length) + matchRows.length) % matchRows.length
      matchCursor.current = next
      const row = matchRows[next]
      centreOnRow(row)
      onSelectCommit?.(nodes[row].commit.hash)
    },
    [matchRows, centreOnRow, nodes, onSelectCommit, containerRef]
  )

  /** Bring the first match into view when the query selects nothing on screen.
   *
   * Scroll only, no selection: swapping the diff pane mid-keystroke is more
   * disruptive than helpful. It runs off the match set, not off scrolling, so
   * scrolling away afterwards leaves the view where you put it. */
  useEffect(() => {
    const container = containerRef.current
    if (!container || matchRows.length === 0) return
    if (anyRowVisible(matchRows, rowToY, rowHeight, container)) return
    centreOnRow(matchRows[0])
    matchCursor.current = 0
  }, [matchRows, rowToY, rowHeight, centreOnRow, containerRef])

  return {
    search,
    setSearch,
    query,
    searching,
    matchCount: matches.size,
    loadedHashes,
    dimOpacity,
    stepMatch,
    showHistorySearch,
    openHistorySearch: useCallback(() => setShowHistorySearch(true), []),
    closeHistorySearch: useCallback(() => setShowHistorySearch(false), []),
  }
}
