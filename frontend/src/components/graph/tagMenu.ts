/** The menu behind a tag badge.
 *
 * Deleting a tag locally is a private act; deleting it on origin takes it away
 * from everyone. So the second item appears only once we know origin actually
 * has this tag, and only it asks for confirmation.
 */
export interface TagMenuItem {
  key: string
  label: string
  danger: boolean
  onClick: () => void
}

export function buildTagMenuItems(
  tag: string,
  remoteTags: Set<string> | null,
  onDelete: (deleteRemote: boolean) => void
): TagMenuItem[] {
  const items: TagMenuItem[] = [
    { key: 'delete-tag', label: 'Delete tag', danger: true, onClick: () => onDelete(false) },
  ]
  if (remoteTags?.has(tag)) {
    items.push({
      key: 'delete-tag-origin',
      label: 'Delete tag on origin too',
      danger: true,
      onClick: () => {
        if (!confirm(`Delete tag "${tag}" on origin?\n\nIt disappears for everyone else too.`))
          return
        onDelete(true)
      },
    })
  }
  return items
}
