/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import FilePicker from './FilePicker'
import type { DiffFile } from './types'

const files: DiffFile[] = [
  { path: 'backend/git_utils.py', diff: '--- a\n+++ b\n+one\n-two\n' },
  { path: 'frontend/src/FileDiff.tsx', diff: '--- a\n+++ b\n+only\n' },
  { path: 'docs/release.md', diff: '--- a\n+++ b\n-gone\n' },
]

afterEach(cleanup)

function open(onSelect = vi.fn()) {
  render(<FilePicker files={files} current={files[0].path} onSelect={onSelect} />)
  fireEvent.click(screen.getByTestId('file-picker-toggle'))
  return { onSelect, input: screen.getByPlaceholderText('Filter 3 files...') }
}

describe('FilePicker', () => {
  it('stays out of the way until asked', () => {
    render(<FilePicker files={files} current={files[0].path} onSelect={vi.fn()} />)

    expect(screen.queryByPlaceholderText('Filter 3 files...')).toBeNull()
  })

  it('lists every file once opened', () => {
    open()

    expect(screen.getAllByTestId('file-picker-option').map((o) => o.textContent)).toEqual([
      'backend/git_utils.py+1-1',
      'frontend/src/FileDiff.tsx+1-0',
      'docs/release.md+0-1',
    ])
  })

  it('narrows to what was typed', () => {
    const { input } = open()

    fireEvent.change(input, { target: { value: 'release' } })

    const listed = screen.getAllByTestId('file-picker-option').map((o) => o.textContent)
    expect(listed).toEqual(['docs/release.md+0-1'])
  })

  it('picks the top match on Enter and closes', () => {
    const { onSelect, input } = open()

    fireEvent.change(input, { target: { value: 'FileDiff' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(onSelect).toHaveBeenCalledWith('frontend/src/FileDiff.tsx')
    expect(screen.queryByPlaceholderText('Filter 3 files...')).toBeNull()
  })

  it('starts each new query at the top match rather than a stale row', () => {
    const { onSelect, input } = open()

    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.change(input, { target: { value: 'git_utils' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(onSelect).toHaveBeenCalledWith('backend/git_utils.py')
  })

  it('closes on Escape without choosing anything', () => {
    const { onSelect, input } = open()

    fireEvent.keyDown(input, { key: 'Escape' })

    expect(onSelect).not.toHaveBeenCalled()
    expect(screen.queryByPlaceholderText('Filter 3 files...')).toBeNull()
  })
})
