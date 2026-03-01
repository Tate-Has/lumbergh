import type { GraphCommit, GraphNode, GraphEdge } from '../diff/types'

const LANE_COLORS = [
  '#4fc3f7', // blue
  '#81c784', // green
  '#ffb74d', // orange
  '#e57373', // red
  '#ba68c8', // purple
  '#4dd0e1', // cyan
  '#fff176', // yellow
  '#f06292', // pink
  '#aed581', // light green
  '#90a4ae', // grey
]

export function laneColor(lane: number): string {
  return LANE_COLORS[lane % LANE_COLORS.length]
}

export function computeGraphLayout(
  commits: GraphCommit[],
  headHash: string | null
): GraphNode[] {
  // activeLanes[i] = hash that lane i is expecting (the parent we're waiting for)
  const activeLanes: (string | null)[] = []
  // Map from hash to row index for connecting edges
  const hashToRow = new Map<string, number>()

  const nodes: GraphNode[] = []

  for (let row = 0; row < commits.length; row++) {
    const commit = commits[row]
    hashToRow.set(commit.hash, row)

    // Find which lane this commit occupies (if any lane is expecting it)
    let lane = activeLanes.indexOf(commit.hash)

    if (lane === -1) {
      // Not expected by any lane — allocate a new one
      lane = activeLanes.indexOf(null)
      if (lane === -1) {
        lane = activeLanes.length
        activeLanes.push(null)
      }
    }

    // This lane is now fulfilled
    activeLanes[lane] = null

    const edges: GraphEdge[] = []

    // Process parents
    for (let p = 0; p < commit.parents.length; p++) {
      const parentHash = commit.parents[p]

      if (p === 0) {
        // First parent continues in the same lane
        activeLanes[lane] = parentHash
        // Edge will be drawn when the parent row is processed, but we record it now
        // as a downward edge from this row in lane
      } else {
        // Other parents: find an existing lane expecting this parent, or allocate new
        let parentLane = activeLanes.indexOf(parentHash)
        if (parentLane === -1) {
          // Allocate a new lane
          parentLane = activeLanes.indexOf(null)
          if (parentLane === -1) {
            parentLane = activeLanes.length
            activeLanes.push(null)
          }
          activeLanes[parentLane] = parentHash
        }
      }
    }

    // Close empty lanes at the end to keep the graph compact
    while (activeLanes.length > 0 && activeLanes[activeLanes.length - 1] === null) {
      activeLanes.pop()
    }

    nodes.push({
      commit,
      lane,
      edges, // edges populated in second pass
      isHead: commit.hash === headHash,
      onCurrentBranch: false, // set in third pass
    })
  }

  // Second pass: compute edges by looking at parent relationships
  for (let row = 0; row < nodes.length; row++) {
    const node = nodes[row]
    for (const parentHash of node.commit.parents) {
      const parentRow = hashToRow.get(parentHash)
      if (parentRow !== undefined) {
        const parentNode = nodes[parentRow]
        node.edges.push({
          fromLane: node.lane,
          toLane: parentNode.lane,
          fromRow: row,
          toRow: parentRow,
        })
      }
    }
  }

  // Third pass: mark commits on the current branch (first-parent chain from HEAD)
  const currentBranchHashes = new Set<string>()
  if (headHash) {
    let hash: string | null = headHash
    while (hash) {
      currentBranchHashes.add(hash)
      const row = hashToRow.get(hash)
      if (row === undefined) break
      // Follow first parent
      hash = commits[row].parents[0] ?? null
    }
  }
  for (const node of nodes) {
    node.onCurrentBranch = currentBranchHashes.has(node.commit.hash)
  }

  return nodes
}
