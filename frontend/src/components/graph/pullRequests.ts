/** Open pull requests, as `gh` reported them to the backend. */
export interface PullRequest {
  number: number
  title: string
  state: string
  url: string
  headRefName: string
  isDraft: boolean
}

/** The branch a ref names. `origin/x` and `x` are the same branch as far as a
 * PR is concerned; another remote's ref is left alone, since its branches are
 * not the ones this repo's PRs are opened from. */
export function refBranchName(name: string): string {
  return name.startsWith('origin/') ? name.slice('origin/'.length) : name
}

export function prsByBranch(prs: PullRequest[]): Map<string, PullRequest> {
  const byBranch = new Map<string, PullRequest>()
  for (const pr of prs) {
    const existing = byBranch.get(pr.headRefName)
    if (!existing || pr.number < existing.number) byBranch.set(pr.headRefName, pr)
  }
  return byBranch
}
