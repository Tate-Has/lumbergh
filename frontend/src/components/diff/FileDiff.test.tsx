/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import FileDiff from './FileDiff'
import { ThemeProvider } from '../../hooks/useTheme'
import type { DiffFile } from './types'

vi.mock('@git-diff-view/react', () => ({
  DiffView: () => <div data-testid="diff-view" />,
  DiffModeEnum: { Unified: 1 },
}))
vi.mock('@git-diff-view/lowlight', () => ({ highlighter: {} }))
vi.mock('@git-diff-view/core', () => ({ _cacheMap: { setMaxLength: () => {} } }))
vi.mock('../MarkdownViewer', () => ({
  default: () => <div data-testid="markdown-modal" />,
  MarkdownBody: ({ content }: { content: string }) => (
    <div data-testid="markdown-body">{content}</div>
  ),
}))

const markdownFile: DiffFile = {
  path: 'docs/notes.md',
  diff: '--- a\n+++ b\n@@ -1 +1 @@\n-old\n+# New\n',
  oldContent: 'old\n',
  newContent: '# New\n',
}

afterEach(cleanup)
beforeEach(() => localStorage.clear())

function renderFile(file: DiffFile = markdownFile) {
  return render(
    <ThemeProvider>
      <FileDiff file={file} onBack={() => {}} />
    </ThemeProvider>
  )
}

describe('inline markdown rendering', () => {
  it('swaps the diff for rendered markdown and back', () => {
    renderFile()
    expect(screen.getByTestId('diff-view')).toBeTruthy()

    fireEvent.click(screen.getByTestId('inline-markdown-toggle'))
    expect(screen.queryByTestId('diff-view')).toBeNull()
    expect(screen.getByTestId('markdown-body').textContent).toBe('# New\n')

    fireEvent.click(screen.getByTestId('inline-markdown-toggle'))
    expect(screen.getByTestId('diff-view')).toBeTruthy()
  })

  it('renders the old content when the file was deleted', () => {
    renderFile({ ...markdownFile, newContent: '' })
    fireEvent.click(screen.getByTestId('inline-markdown-toggle'))
    expect(screen.getByTestId('markdown-body').textContent).toBe('old\n')
  })

  it('remembers the choice for the next markdown file', () => {
    renderFile()
    fireEvent.click(screen.getByTestId('inline-markdown-toggle'))
    cleanup()
    renderFile()
    expect(screen.getByTestId('markdown-body')).toBeTruthy()
  })

  it('offers no toggle for non-markdown files', () => {
    renderFile({ ...markdownFile, path: 'backend/git_utils.py' })
    expect(screen.queryByTestId('inline-markdown-toggle')).toBeNull()
  })
})
