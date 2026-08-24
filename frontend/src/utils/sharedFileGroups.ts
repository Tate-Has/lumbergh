export interface SharedFile {
  name: string
  size: number
  modified: number
}

export type TimeGroup = 'Today' | 'Yesterday' | '2 Days Ago' | 'This Week' | 'Older'

export interface FileGroup {
  group: TimeGroup
  files: SharedFile[]
  /** Newest mtime (epoch seconds) that does NOT belong to this group — everything below it is this group or older. */
  cutoff: number
}

const DAY_SECONDS = 86400

/** Newest-first, each entry the oldest mtime (epoch seconds) still in that group. */
function groupStarts(now: Date): { group: TimeGroup; start: number }[] {
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000
  return [
    { group: 'Today', start: todayStart },
    { group: 'Yesterday', start: todayStart - DAY_SECONDS },
    { group: '2 Days Ago', start: todayStart - 2 * DAY_SECONDS },
    { group: 'This Week', start: todayStart - 7 * DAY_SECONDS },
    { group: 'Older', start: -Infinity },
  ]
}

export function groupFilesByTime(files: SharedFile[], now: Date = new Date()): FileGroup[] {
  const starts = groupStarts(now)
  const grouped = new Map<TimeGroup, SharedFile[]>()
  for (const file of files) {
    const { group } =
      starts.find(({ start }) => file.modified >= start) ?? starts[starts.length - 1]
    if (!grouped.has(group)) grouped.set(group, [])
    grouped.get(group)!.push(file)
  }
  return starts
    .map(({ group }, index) => ({
      group,
      files: grouped.get(group) ?? [],
      cutoff: index === 0 ? Infinity : starts[index - 1].start,
    }))
    .filter(({ files }) => files.length > 0)
}
