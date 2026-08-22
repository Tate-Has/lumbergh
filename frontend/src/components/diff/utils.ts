import type { Commit, CommitDiff, FileStats } from './types'

/** The header for the commit the graph has selected, or null while there is none.
 *
 * The graph abbreviates hashes to 12 chars on the wire but the commit endpoint
 * answers with the full 40, so the two are compared by prefix: an equality check
 * silently hid the whole commit header, send-to-terminal button included.
 */
export function commitHeaderInfo(
  commitData: CommitDiff | null,
  selectedHash: string | null
): Commit | null {
  if (!selectedHash || !commitData?.hash.startsWith(selectedHash)) return null
  return {
    hash: commitData.hash,
    shortHash: commitData.hash.slice(0, 7),
    message: commitData.message,
    author: commitData.author,
    relativeDate: commitData.relativeDate,
  }
}

// Extract the diff content starting from --- line
// The library expects: --- a/file\n+++ b/file\n@@ ... @@\n...
export function extractDiffContent(diff: string): string[] {
  const lines = diff.split('\n')
  const result: string[] = []
  let started = false

  for (const line of lines) {
    if (line.startsWith('--- ')) {
      started = true
    }
    if (started) {
      result.push(line)
    }
  }

  return result.length > 0 ? [result.join('\n')] : []
}

// Calculate per-file stats from diff content
export function getFileStats(diff: string): FileStats {
  const lines = diff.split('\n')
  let additions = 0
  let deletions = 0

  for (const line of lines) {
    if (line.startsWith('+') && !line.startsWith('+++')) {
      additions++
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      deletions++
    }
  }

  return { additions, deletions }
}

// Language hint for the diff highlighter, derived from the file extension.
// The bare extension is passed straight through: @git-diff-view/lowlight is
// built with the full highlight.js language set and resolves extensions to
// languages via its own alias table (py -> python, rs -> rust, feature ->
// gherkin, ...), falling back to content auto-detection for anything it does
// not recognize. New file types highlight automatically, no map to maintain.
export function getLangFromPath(path: string): string {
  return path.split('.').pop()?.toLowerCase() || 'plaintext'
}

/** What the one-click review button types into the terminal.
 *
 * Sent unsent (send_enter false) so it lands on the prompt line as a starting
 * point — "Review <path>" is the common case, and anything more specific is a
 * few keystrokes away.
 */
export function reviewFilePrompt(path: string): string {
  return `Review ${path}`
}
