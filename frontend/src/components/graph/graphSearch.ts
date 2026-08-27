import type { GraphCommit } from '../diff/types'

export interface SearchQuery {
  /** Free text, matched against message, author, hash, and ref names. */
  text: string
  author?: string
  /** A pathspec. The graph payload carries no file lists, so this forces a history search. */
  file?: string
  needsHistory: boolean
}

/** The graph payload abbreviates hashes to 12 chars; history search returns
 *  full 40-char ones. Compare commits from the two sources on this key. */
const HASH_KEY_LENGTH = 12

export function hashKey(hash: string): string {
  return hash.slice(0, HASH_KEY_LENGTH)
}

const QUALIFIER = /\b(author|file):(?:"([^"]*)"|(\S+))/g

export function parseQuery(raw: string): SearchQuery {
  const qualifiers: Record<string, string> = {}
  const text = raw
    .replace(QUALIFIER, (_match, key: string, quoted?: string, bare?: string) => {
      qualifiers[key] = quoted ?? bare ?? ''
      return ''
    })
    .trim()
    .replace(/\s+/g, ' ')

  return {
    text,
    author: qualifiers.author,
    file: qualifiers.file,
    needsHistory: qualifiers.file !== undefined,
  }
}

export function isEmptyQuery(query: SearchQuery): boolean {
  return query.text === '' && query.author === undefined && query.file === undefined
}

function haystack(commit: GraphCommit): string {
  const refs = commit.refs.map((ref) => ref.name).join(' ')
  return `${commit.message} ${commit.author} ${commit.hash} ${refs}`.toLowerCase()
}

function matches(commit: GraphCommit, query: SearchQuery): boolean {
  if (query.author !== undefined) {
    const author = `${commit.author} ${commit.authorEmail ?? ''}`.toLowerCase()
    if (!author.includes(query.author.toLowerCase())) return false
  }
  if (query.text === '') return true
  return haystack(commit).includes(query.text.toLowerCase())
}

/** Hashes of the commits a query selects. Empty when nothing local can answer it. */
export function findMatches(commits: GraphCommit[], query: SearchQuery): Set<string> {
  if (isEmptyQuery(query) || query.needsHistory) return new Set()
  return new Set(commits.filter((commit) => matches(commit, query)).map((c) => c.hash))
}

/** Is any of these rows currently on screen? A row counts when it overlaps the
 *  viewport at all, so one scrolled half out of view still counts as seen. */
export function anyRowVisible(
  rows: number[],
  rowToY: (row: number) => number,
  rowHeight: number,
  viewport: { scrollTop: number; clientHeight: number }
): boolean {
  const top = viewport.scrollTop
  const bottom = top + viewport.clientHeight
  return rows.some((row) => {
    const y = rowToY(row)
    return y + rowHeight > top && y < bottom
  })
}
