import React from 'react'
import { Trash2 } from 'lucide-react'

import { confirmHardReset, resetMenuEntries } from './resetMenu'
import type { ResetMode } from './resetMenu'

export type BranchMenuItem = {
  key: string
  label: React.ReactNode
  onClick: () => void
  danger?: boolean
  separator?: boolean
}

export type MenuBranchInfo = {
  name: string
  local: boolean
  remote: boolean
  commitHash: string
  commitShortHash: string
  x: number
  y: number
}

export function buildBranchMenuItems(
  menuBranch: MenuBranchInfo,
  isCurrent: boolean,
  hasUnpushed: boolean | undefined,
  handleBranchCheckout: () => void,
  handleBranchPush: () => void,
  handleResetTo: (hash: string, mode: ResetMode) => void,
  setDeleteBranchConfirm: (v: { name: string; local: boolean; remote: boolean } | null) => void,
  setMenuBranch: (v: MenuBranchInfo | null) => void
): BranchMenuItem[] {
  const items: BranchMenuItem[] = []
  if (!isCurrent) {
    items.push({ key: 'checkout', label: 'Checkout', onClick: handleBranchCheckout })
  }
  if (hasUnpushed && menuBranch.local) {
    items.push({ key: 'push', label: 'Push', onClick: handleBranchPush })
  }
  if (!menuBranch.local && menuBranch.remote) {
    const target = `${menuBranch.name} (${menuBranch.commitShortHash})`
    items.push(
      ...resetMenuEntries(
        () => {
          if (!confirmHardReset(target)) return
          handleResetTo(menuBranch.commitHash, 'hard')
        },
        () => {
          if (!confirm(`Reset current branch to ${target}?`)) return
          handleResetTo(menuBranch.commitHash, 'soft')
        }
      )
    )
  }
  if (!isCurrent) {
    items.push({
      key: 'delete',
      separator: true,
      danger: true,
      label: (
        <>
          <Trash2 size={14} />
          Delete branch
        </>
      ),
      onClick: () => {
        setDeleteBranchConfirm({
          name: menuBranch.name,
          local: menuBranch.local,
          remote: menuBranch.remote,
        })
        setMenuBranch(null)
      },
    })
  }
  return items
}
