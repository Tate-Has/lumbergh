/** Filter a diff's file paths by a typed query.
 *
 * A filename match outranks a directory match: someone typing "diff" while
 * looking for `other/diff.ts` should not have to scroll past every file that
 * merely lives in a `diff/` folder.
 */
export function filterFiles(paths: string[], query: string): string[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return paths

  const matches = paths.filter((p) => p.toLowerCase().includes(needle))
  const inFilename = (p: string) => (p.split('/').pop() ?? p).toLowerCase().includes(needle)
  return [...matches.filter(inFilename), ...matches.filter((p) => !inFilename(p))]
}
