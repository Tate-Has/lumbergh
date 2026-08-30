import type { Commit, CommitDiff, CommitRange, FileStats } from './types'

/** What the diff viewer's header describes: one commit, or a comparison of two. */
export interface DiffHeader extends Commit {
  /** Set when the header describes a range, and the labels should say so. */
  compare?: CommitRange
}

/** Does an abbreviated hash from the graph name this commit?
 *
 * The graph abbreviates hashes to 12 chars on the wire but the commit endpoint
 * answers with the full 40, so the two are compared by prefix: an equality check
 * silently hid the whole commit header, send-to-terminal button included.
 */
function namesCommit(fullHash: string, abbreviated: string): boolean {
  return fullHash.startsWith(abbreviated)
}

/** The header for what the graph has selected, or null while there is none. */
export function commitHeaderInfo(
  commitData: CommitDiff | null,
  selectedHash: string | null,
  compareHash?: string | null
): DiffHeader | null {
  if (!selectedHash || !commitData) return null

  if (compareHash) {
    const range = commitData.range
    if (!range) return null
    const endpoints = [range.from.hash, range.to.hash]
    const named = [selectedHash, compareHash].every((h) =>
      endpoints.some((endpoint) => namesCommit(endpoint, h))
    )
    if (!named) return null
    return {
      hash: `${range.from.hash}..${range.to.hash}`,
      shortHash: `${range.from.shortHash}..${range.to.shortHash}`,
      message: `${range.commitCount} commit${range.commitCount === 1 ? '' : 's'}`,
      author: range.to.author,
      relativeDate: range.to.relativeDate,
      compare: range,
    }
  }

  if (!namesCommit(commitData.hash, selectedHash)) return null
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
