import ViewToggle from './ViewToggle'

export default function TabBar() {
  return (
    <div
      className="flex items-center justify-center px-4 py-2 bg-bg-base border-b border-border-default"
      style={{ paddingTop: 'max(8px, env(safe-area-inset-top))' }}
    >
      <ViewToggle />
    </div>
  )
}
