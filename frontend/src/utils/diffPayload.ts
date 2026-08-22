import type { DiffData } from '../components/diff/types'

/** A diff payload, or null for anything that is not one.
 *
 * A failing git endpoint answers `{detail: "..."}`; stored unchecked, that
 * reaches the viewer as a diff with no `files`, and reading `files.length`
 * throws hard enough to blank the whole app. Nothing enters state without
 * looking like a diff first.
 */
export function parseDiffPayload(payload: unknown): DiffData | null {
  if (!payload || typeof payload !== 'object') return null
  const files = (payload as { files?: unknown }).files
  if (!Array.isArray(files)) return null
  const stats = (payload as { stats?: DiffData['stats'] }).stats
  return {
    files: files as DiffData['files'],
    stats: stats ?? { additions: 0, deletions: 0 },
  }
}
