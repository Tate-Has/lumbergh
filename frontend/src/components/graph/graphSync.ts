import type { GraphCommit, GraphData } from '../diff/types'

/** What the API can send back for a graph request. */
export type GraphResponse =
  | ({ unchanged: true; version: string } & Partial<GraphData>)
  | (GraphData & { reset?: true })
  | ({
      delta: true
      version: string
      added: GraphCommit[]
      /** Explicit ordering, sent only when `keep` cannot describe the change. */
      order?: string[]
      /** Shorthand: the new list is `added` followed by this many of the ones we hold. */
      keep?: number
    } & Omit<GraphData, 'commits' | 'version'>)

/**
 * `shortHash` is not sent — it is a duplicate of data already in `hash`, on a
 * payload where hashes are random hex and survive gzip at full price.
 */
function withShortHash(commits: GraphCommit[]): GraphCommit[] {
  for (const commit of commits) commit.shortHash = commit.hash.slice(0, 7)
  return commits
}

/**
 * Fold a response into the graph the client is already holding.
 *
 * Returns the graph to render and whether the cursor survived. A `false` cursor
 * means the next poll must ask for a full keyframe — either the server sent a
 * delta we cannot apply, or applying it produced a graph that disagrees with
 * the order the server described. Both are cheap to recover from and dangerous
 * to paper over, so they degrade to a re-fetch rather than to a wrong graph.
 */
export function applyGraphResponse(
  previous: GraphData | null,
  response: GraphResponse
): { graph: GraphData | null; cursorValid: boolean } {
  if ('unchanged' in response && response.unchanged) {
    return { graph: previous, cursorValid: true }
  }

  if ('delta' in response && response.delta) {
    if (!previous) return { graph: previous, cursorValid: false }

    const { delta: _delta, added, order, keep, ...rest } = response
    withShortHash(added)

    if (order === undefined) {
      if (keep === undefined || keep > previous.commits.length) {
        return { graph: previous, cursorValid: false }
      }
      const commits = [...added, ...previous.commits.slice(0, keep)]
      return { graph: { ...previous, ...rest, commits }, cursorValid: true }
    }

    const byHash = new Map(previous.commits.map((commit) => [commit.hash, commit]))
    for (const commit of added) byHash.set(commit.hash, commit)
    const commits = order.map((hash) => byHash.get(hash)).filter((c): c is GraphCommit => !!c)
    if (commits.length !== order.length) {
      return { graph: previous, cursorValid: false }
    }
    return { graph: { ...previous, ...rest, commits }, cursorValid: true }
  }

  const keyframe = response as GraphData
  withShortHash(keyframe.commits)
  return { graph: keyframe, cursorValid: true }
}
