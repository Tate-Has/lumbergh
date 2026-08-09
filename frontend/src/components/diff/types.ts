export interface DiffFile {
  path: string
  diff: string
  oldContent?: string | null
  newContent?: string | null
}

export interface Commit {
  hash: string
  shortHash: string
  message: string
  author: string
  relativeDate: string
}

export interface CommitDiff extends Commit {
  files: DiffFile[]
  stats: {
    additions: number
    deletions: number
  }
}

export interface DiffData {
  files: DiffFile[]
  stats: {
    additions: number
    deletions: number
  }
}

export interface FileStats {
  additions: number
  deletions: number
}

export interface Branch {
  name: string
  current?: boolean
  remote?: string
}

export interface BranchData {
  current: string
  local: Branch[]
  remote: Branch[]
  clean: boolean
}

// Git graph types

export interface GraphCommit {
  /** Abbreviated to 12 chars on the wire; git resolves it wherever we hand it back. */
  hash: string
  /** Not sent by the API — derived from `hash` when the payload is parsed. */
  shortHash: string
  message: string
  author: string
  authorEmail?: string
  authorGravatar?: string
  relativeDate: string
  parents: string[]
  refs: { name: string; local: boolean; remote: boolean; tag?: boolean; stash?: boolean }[]
  pushed?: boolean
  stash?: boolean
}

export interface GraphWorktree {
  branch: string
  /** 7-char short hash — matches the start of a GraphCommit's abbreviated hash. */
  headHash: string
  path: string
  isMain: boolean
  isCurrent: boolean
  sessionName: string | null
}

export interface GraphData {
  commits: GraphCommit[]
  branches: { name: string; hash: string; current: boolean }[]
  head: { hash: string; branch: string | null } | null
  workingChanges: { files: number; staged: number; unstaged: number } | null
  worktrees?: GraphWorktree[]
  /** `available` is false when no git identity could be resolved, which
   *  disables the "just mine" filter rather than showing an empty graph. */
  mine?: { available: boolean; active: boolean }
}

export interface GraphEdge {
  fromLane: number
  toLane: number
  fromRow: number
  toRow: number
}

export interface GraphNode {
  commit: GraphCommit
  lane: number
  edges: GraphEdge[]
  isHead: boolean
  onCurrentBranch: boolean
}
