interface ToastProps {
  message: string
  visible: boolean
}

export default function Toast({ message, visible }: ToastProps) {
  return (
    <div
      className={`toast fixed bottom-4 right-4 bg-bg-elevated border border-border-default rounded-lg px-3.5 py-2 text-[0.78rem] font-medium text-text-secondary shadow-modal transition-all duration-200 ease-in-out pointer-events-none z-[200] ${visible ? ' visible opacity-100 translate-y-0' : ' opacity-0 translate-y-[10px]'}`}
      id="toast"
    >
      {message}
    </div>
  )
}
