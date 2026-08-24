import { describe, it, expect } from 'vitest'
import { groupFilesByTime } from './sharedFileGroups'

const NOW = new Date(2026, 7, 23, 14, 30)
const MIDNIGHT = new Date(2026, 7, 23).getTime() / 1000
const DAY = 86400

function file(name: string, modified: number) {
  return { name, size: 1, modified }
}

describe('groupFilesByTime', () => {
  it('buckets files by how long ago they were touched', () => {
    const groups = groupFilesByTime(
      [
        file('today.md', MIDNIGHT + 60),
        file('yesterday.md', MIDNIGHT - 60),
        file('two-days.md', MIDNIGHT - DAY - 60),
        file('this-week.md', MIDNIGHT - 3 * DAY),
        file('ancient.md', MIDNIGHT - 30 * DAY),
      ],
      NOW
    )

    expect(groups.map((g) => [g.group, g.files.map((f) => f.name)])).toEqual([
      ['Today', ['today.md']],
      ['Yesterday', ['yesterday.md']],
      ['2 Days Ago', ['two-days.md']],
      ['This Week', ['this-week.md']],
      ['Older', ['ancient.md']],
    ])
  })

  it('omits groups with no files', () => {
    const groups = groupFilesByTime([file('ancient.md', MIDNIGHT - 30 * DAY)], NOW)
    expect(groups.map((g) => g.group)).toEqual(['Older'])
  })

  it('gives each group a cutoff that covers exactly that group and everything older', () => {
    const files = [
      file('today.md', MIDNIGHT + 60),
      file('yesterday.md', MIDNIGHT - 60),
      file('two-days.md', MIDNIGHT - DAY - 60),
      file('this-week.md', MIDNIGHT - 3 * DAY),
      file('ancient.md', MIDNIGHT - 30 * DAY),
    ]
    const groups = groupFilesByTime(files, NOW)

    const doomedBy = (group: string) => {
      const cutoff = groups.find((g) => g.group === group)!.cutoff
      return files.filter((f) => f.modified < cutoff).map((f) => f.name)
    }

    expect(doomedBy('Yesterday')).toEqual([
      'yesterday.md',
      'two-days.md',
      'this-week.md',
      'ancient.md',
    ])
    expect(doomedBy('2 Days Ago')).toEqual(['two-days.md', 'this-week.md', 'ancient.md'])
    expect(doomedBy('This Week')).toEqual(['this-week.md', 'ancient.md'])
    expect(doomedBy('Older')).toEqual(['ancient.md'])
  })
})
